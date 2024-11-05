const express = require('express');
const WebSocket = require('ws');
const mariadb = require('mariadb');
const cors = require('cors');

// Initialize the Express application
const app = express();
const port = 3000;  // Port number for the server
const nbSondes = 5; // Number of sensors
//const allowedOrigins = ['http://localhost:3000/historisation.html']; // List of allowed origins for CORS
const allowedOrigins = ['*']; // List of allowed origins for CORS

// CORS configuration options
const corsOptions = {
    origin: (origin, callback) => {
        // Check if the request origin is allowed
        if (!origin || allowedOrigins.includes(origin)) {
            callback(null, true);
        } else {
            callback(new Error('Not allowed by CORS'));
        }
    },
    methods: ['GET', 'POST'], // Allowed HTTP methods
    credentials: false // Disabling credentials
};

// Apply CORS middleware
app.use(cors(corsOptions));
app.use(express.json()); // Middleware to parse JSON request bodies
app.use(express.static('public')); // Serve static files from the 'public' directory

// Create a MariaDB connection pool
const pool = mariadb.createPool({
    host: "localhost",
    user: "root",
    password: "v1veP1lou",
    database: "sonometre",
    connectionLimit: 20 // Maximum number of connections in the pool
});

// Create an HTTP server and WebSocket server
const server = require('http').createServer(app);
const wss = new WebSocket.Server({ server });

// Default sensor data when no data is available
const defaultSensorData = {
    temperature: -1,
    humidite: -1,
    co2: -1,
    compose_organic_volatile: -1,
    decibels: -1,
    particules_fines: -1
};

// Function to fetch data from the database
const fetchData = async (query, params = []) => {
    let conn;
    try {
        conn = await pool.getConnection(); // Get a connection from the pool
        const results = await conn.query(query, params); // Execute the query
        return results;
    } catch (err) {
        console.error('Database error:', err); // Log database errors
        throw err;
    } finally {
        if (conn) conn.end(); // Ensure the connection is closed
    }
};

// Function to send sensor data to all connected WebSocket clients
const sendSensorData = async () => {
    try {
        // Fetch the most recent sensor data
        const results = await fetchData('SELECT * FROM sensor_data_real_time ORDER BY sonde DESC LIMIT ?', [nbSondes]);
        // Prepare the sensor data for sending
        const sensorData = Array.from({ length: nbSondes }, (_, i) => results.find(row => row.sonde === i + 1) || { sonde: i + 1, ...defaultSensorData });
        // Send the data to each connected WebSocket client
        wss.clients.forEach(client => {
            if (client.readyState === WebSocket.OPEN) {
                client.send(JSON.stringify(sensorData.reduce((acc, curr) => ({ ...acc, [curr.sonde]: curr }), {})));
            }
        });
    } catch (err) {
        console.error('Error fetching sensor data:', err); // Log errors in fetching data
    }
};

// Route to get historical data
app.get('/historic-data', async (req, res) => {
    const { start, end, sondes, measure } = req.query; // Extract query parameters
    const selectedSondes = sondes.split(',').map(Number); // Convert the list of sondes to an array of numbers
    const query = `
        SELECT * FROM sensor_data_historic 
        WHERE timestamp BETWEEN ? AND ? 
        AND sonde IN (?) 
        AND if((?)<now()- interval 24 hour,if((?)<now() - interval 7 day ,3600,60),1)=poids
        AND ${measure} > 0`;

    try {
        // Fetch historical data from the database
        const rows = await fetchData(query, [new Date(start), new Date(end), selectedSondes,new Date(start),new Date(start)]);
	console.log("StartDate: " + new Date(start));
	console.log("EndDate: " + new Date(end));
	console.log("Nodes: " + selectedSondes);
        console.debug("Length rows: " + rows.length)
        // Format and send the data as JSON
        res.json(formatData(rows, measure));
    } catch (err) {
        res.status(500).send('Server error'); // Send a server error response on failure
    }
});

// Function to format the data for response
const formatData = (rows, measure) => rows.reduce((acc, row) => {
    if (!acc[row.sonde]) {
        acc[row.sonde] = {
            dates: [],
            temperature: [],
            humidite: [],
            co2: [],
            compose_organic_volatile: [],
            decibels: [],
            particules_fines: []
        };
    }
    acc[row.sonde].dates.push(row.timestamp);
    acc[row.sonde][measure].push(row[measure]);
    return acc;
}, {});

// WebSocket connection handler
wss.on('connection', ws => {
    console.log('Client connected');
    ws.on('close', () => console.log('Client disconnected')); 
});

// Serve the index.html file at the root URL
app.get('/', (req, res) => res.sendFile(__dirname + '/public/index.html'));
// Serve the historisation.html file at the /historisation URL
app.get('/historisation', (req, res) => res.sendFile(__dirname + '/public/historisation.html'));
// Handle POST requests to /notify by sending sensor data
app.post('/notify', (req, res) => {
    sendSensorData();
    res.sendStatus(200); // Send a success status
});

// Start the server
server.listen(port, () => console.log(`Server running at http://localhost:${port}/`));
