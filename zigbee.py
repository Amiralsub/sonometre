import asyncio
import logging
import signal
import sys
import requests
from collections import defaultdict
from sensor import display_readings
from database import insert_real_time_data, insert_historic_data, get_pool
from zigpy_znp.zigbee.application import ControllerApplication
from zigpy_znp.config import CONFIG_SCHEMA
from zigpy.types import EUI64

# Set up logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration settings
CONFIG = {
    'device': {
        'path': '/dev/ttyUSB0',  # Path to the serial port for the Zigbee coordinator
        'baudrate': 115200,      # Baud rate for serial communication
    },
    'znp_config': {
        'tx_power': 14,                         # Transmit power of the Zigbee device max 22 https://community.home-assistant.io/t/iteads-sonoff-zigbee-3-0-usb-dongle-plus-model-zbdongle-p-based-on-texas-instruments-cc2652p-radio-soc-mcu/340705/189?page=10
        'auto_reconnect_retry_delay': 5,        # Delay in seconds before retrying to reconnect
        'skip_bootloader': True,                # Whether to skip bootloader
        'prefer_endpoint_1': True,              # Whether to prefer endpoint 1
        'led_mode':'OFF',
        'connect_rts_pin_states': [False, True, False],  # RTS pin states for connection
        'connect_dtr_pin_states': [False, False, False],  # DTR pin states for connection
    },
    'ieee_addresses': [
        "74:4d:bd:ff:fe:60:1e:ba",  # Device 1: Unique IEEE address for the first sensor
        "74:4d:bd:ff:fe:60:27:e5",  # Device 2: Unique IEEE address for the second sensor
        "74:4d:bd:ff:fe:60:2b:2e",  # Device 3: Unique IEEE address for the third sensor
        "74:4d:bd:ff:fe:60:37:1e",  # Device 4: Unique IEEE address for the fourth sensor
        "74:4d:bd:ff:fe:60:2f:1b"   # Device 5: Unique IEEE address for the fifth sensor
    ],
    'ota': {
        'enabled': False,
        'disable_default_providers': [],
        'providers': [],
        'broadcast_enabled': False,
        'extra_providers': [],
    },
    'endpoints': {
        "temperature": 1,  # Endpoint ID for reading temperature data
        "humidite": 2,     # Endpoint ID for reading humidity data
        "co2": 4,          # Endpoint ID for reading CO2 levels
        "compose_organic_volatile": 3,  # Endpoint ID for reading volatile organic compounds (VOC) levels
        "decibels": 5,     # Endpoint ID for reading decibel levels
        "particules_fines": 7  # Endpoint ID for reading fine particle levels
    },
    'max_failures': 3,       # Maximum number of consecutive failures before giving up on a device
    'retry_interval': 10,    # Interval in seconds between retry attempts for failed devices
    'value_historic': 60     # Interval in iterations for storing historic data
}

# Signal handler for graceful shutdown
def signal_handler(sig, frame):
    print("\nStopping the program...")
    sys.exit(0)

# Register signal handlers for termination signals
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Function to notify updates via HTTP POST request
async def notify_update(data):
    try:
        response = requests.post('http://localhost:3000/notify', json=data)
        response.raise_for_status()
        logger.debug(f"Notification sent: {data}")
    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP POST request failed: {e}")

# Main asynchronous function to run the application
async def main():
    logger.info("Starting the program")

    try:
        config = CONFIG_SCHEMA(CONFIG)  # Validate and load configuration
    except Exception as e:
        logger.error(f"Configuration error: {e}")
        return

    try:
        app = ControllerApplication(config)
    except Exception as e:
        logger.error(f"Failed to create ControllerApplication: {e}")
        logger.debug(f"Configuration used: {config}")
        return
    try:
        await app.startup(auto_form=True)  # Start up the Zigbee application
        # Initialize sensor values and failure counters
        sensor_values = [{"temperature": -1, "humidite": -1, "co2": -1, "compose_organic_volatile": -1, "decibels": -1, "particules_fines": -1} for _ in range(len(CONFIG['ieee_addresses']))]
        failure_counters = [0] * len(CONFIG['ieee_addresses'])

        data_buffers = defaultdict(lambda: {"temperature": [], "humidite": [], "co2": [], "compose_organic_volatile": [], "decibels": [], "particules_fines": []})

        iteration_count = 0

        while True:
            iteration_count += 1
            connected_devices_count = 0 

            for index, address in enumerate(CONFIG['ieee_addresses'], start=1):
                logger.debug(f"Checking device {index} IEEE: {address}, failure count: {failure_counters[index - 1]}")

                if failure_counters[index - 1] >= CONFIG['max_failures']:
                    if iteration_count % CONFIG['retry_interval'] != 0:
                        logger.info(f"Device {index} IEEE: {address} is not connected. Skipping attempts.")
                        continue
                    else:
                        logger.info(f"Retrying connection for Device {index} IEEE: {address}")
                        check_all_sensors = False
                else:
                    check_all_sensors = True

                try:
                    device = app.get_device(ieee=EUI64.convert(address))
                    device_connected = await display_readings(CONFIG['endpoints'], index, device, app, address, sensor_values, check_all_sensors)

                    if device_connected:
                        connected_devices_count += 1  # Increment counter for connected devices
                        failure_counters[index - 1] = 0  # Reset failure counter on successful connection
                        pool = await get_pool()
                        await insert_real_time_data(pool, sensor_values[index - 1], index, notify_update)

                        # Store data in buffers for future historical calculations
                        for measurement in sensor_values[index - 1]:
                            data_buffers[index][measurement].append(sensor_values[index - 1][measurement])

                        # Periodically insert historical data
                        if iteration_count % CONFIG['value_historic'] == 0:
                            avg_values = {}
                            for measurement in sensor_values[index - 1]:
                                # Filter out values that are -1
                                valid_values = [value for value in data_buffers[index][measurement] if value != -1]
                                if valid_values:  # Only calculate the average if there are valid values
                                    avg_values[measurement] = sum(valid_values) / len(valid_values)
                                else:
                                    avg_values[measurement] = -1  # Set average to -1 if no valid values are present

                            await insert_historic_data(pool, avg_values, index) # insere dans la table sensor_data_historic toutes les interval 60sec par défaut 
                            # Clear the buffer after storing historical data
                            data_buffers[index] = {key: [] for key in data_buffers[index]}

                    else:
                        raise Exception("Device not connected")
                except Exception as e:
                    logger.error(f"Error handling device {index} IEEE: {address}")
                    if failure_counters[index - 1] >= CONFIG['max_failures']:
                        logger.info(f"Device {index} IEEE: {address} has exceeded the maximum number of retries.")
                    logger.debug(f"Exception details: {e}", exc_info=True)
                    sensor_values[index - 1] = {"temperature": -1, "humidite": -1, "co2": -1, "compose_organic_volatile": -1, "decibels": -1, "particules_fines": -1}
                    pool = await get_pool()
                    await insert_real_time_data(pool, sensor_values[index - 1], index, notify_update)
                    failure_counters[index - 1] += 1
                    

            # Wait 1 second between iterations if less than 3 devices are connected
            if connected_devices_count < 3:
                await asyncio.sleep(1)

    except asyncio.TimeoutError:
        logger.error("The device took too long to respond.")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    finally:
        await app.shutdown()  # Ensure the application shuts down gracefully

print("Starting the program")
if __name__ == "__main__":
    asyncio.run(main())
