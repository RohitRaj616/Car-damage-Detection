import mysql.connector as connector
import config
import json

try:
    connection = connector.connect(**config.mysql_credentials)
    cursor = connection.cursor()

    print("Connected to MySQL Database.")

    # Load JSON file
    with open('car_parts_prices.json', 'r') as file:
        car_parts_prices = json.load(file)

    # Insert data into car_parts table
    for brand, models in car_parts_prices.items():
        for model, parts in models.items():
            for part_name, price in parts.items():
                cursor.execute("""
                    INSERT INTO car_parts (brand, model, part_name, price)
                    VALUES (%s, %s, %s, %s)
                """, (brand, model, part_name, price))

    connection.commit()
    print("Car parts data inserted successfully!")

except connector.Error as e:
    print(f"Error: {e}")

finally:
    if connection.is_connected():
        cursor.close()
        connection.close()
        print("MySQL connection closed.")