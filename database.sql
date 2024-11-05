-- Créer la base de données si elle n'existe pas
CREATE DATABASE IF NOT EXISTS sonometre;
USE sonometre;

-- ----------------------------------
-- Création de la table sensor_data_real_time
-- ----------------------------------
DROP TABLE IF EXISTS sensor_data_real_time;
CREATE TABLE sensor_data_real_time (
    sonde INT PRIMARY KEY,
    temperature FLOAT,
    humidite FLOAT,
    co2 FLOAT,
    compose_organic_volatile FLOAT,
    decibels FLOAT,
    particules_fines FLOAT
);

-- ----------------------------------
-- Création de la table sensor_data_historic avec partitionnement
-- ----------------------------------
DROP TABLE IF EXISTS sensor_data_historic;
CREATE TABLE sensor_data_historic (
    id INT NOT NULL AUTO_INCREMENT,
    sonde INT,
    temperature FLOAT,
    humidite FLOAT,
    co2 FLOAT,
    compose_organic_volatile FLOAT,
    decibels FLOAT,
    particules_fines FLOAT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    partition_key INT,  -- Colonne pour le partitionnement
    PRIMARY KEY (id, partition_key)  -- Inclure partition_key dans la clé primaire
)
PARTITION BY RANGE (partition_key) (
    PARTITION p202401 VALUES LESS THAN (202402),
    PARTITION p202402 VALUES LESS THAN (202403),
    PARTITION p202403 VALUES LESS THAN (202404),
    PARTITION p202404 VALUES LESS THAN (202405),
    PARTITION p202405 VALUES LESS THAN (202406),
    PARTITION p202406 VALUES LESS THAN (202407),
    PARTITION p202407 VALUES LESS THAN (202408),
    PARTITION p202408 VALUES LESS THAN (202409),
    PARTITION p9999 VALUES LESS THAN MAXVALUE
);

CREATE TABLE IF NOT EXISTS sensor_data_weekly_avg (
    id INT NOT NULL AUTO_INCREMENT,
    sonde INT,
    avg_temperature FLOAT,
    avg_humidite FLOAT,
    avg_co2 FLOAT,
    avg_compose_organic_volatile FLOAT,
    avg_decibels FLOAT,
    avg_particules_fines FLOAT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
);

-- activer le scheduler dans le fichier de conf mariadb
-- [mysqld]
-- event_scheduler = ON
