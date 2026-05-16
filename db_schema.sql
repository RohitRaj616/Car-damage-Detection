CREATE DATABASE IF NOT EXISTS car_damage_detection;
USE car_damage_detection;

-- ================= USERS =================
CREATE TABLE users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    contact_number VARCHAR(10) NOT NULL,
    address VARCHAR(150) NOT NULL,
    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ================= VEHICLES =================
CREATE TABLE vehicles (
    vehicle_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    vehicle_number VARCHAR(50) UNIQUE NOT NULL,
    brand VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,

    FOREIGN KEY (user_id)
        REFERENCES users(user_id)
        ON DELETE CASCADE
);

-- ================= DAMAGE IMAGES =================
CREATE TABLE damage_images (
    image_id INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_id INT NOT NULL,
    image_path VARCHAR(255) NOT NULL,
    upload_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (vehicle_id)
        REFERENCES vehicles(vehicle_id)
        ON DELETE CASCADE
);

-- ================= CAR PARTS =================
CREATE TABLE car_parts (
    part_id INT AUTO_INCREMENT PRIMARY KEY,
    brand VARCHAR(50) NOT NULL,
    model VARCHAR(50) NOT NULL,
    part_name VARCHAR(50) NOT NULL,
    price INT NOT NULL
);

-- ================= DAMAGE REPORTS =================
CREATE TABLE damage_reports (
    report_id INT AUTO_INCREMENT PRIMARY KEY,
    image_id INT NOT NULL,
    part_id INT NOT NULL,
    damage_count INT NOT NULL,
    total_cost INT NOT NULL,

    FOREIGN KEY (image_id)
        REFERENCES damage_images(image_id)
        ON DELETE CASCADE,

    FOREIGN KEY (part_id)
        REFERENCES car_parts(part_id)
        ON DELETE CASCADE
);