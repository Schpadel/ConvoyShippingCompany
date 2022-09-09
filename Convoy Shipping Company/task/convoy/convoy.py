import pandas
import pandas as pd
import re
import sqlite3
import csv
import json
import dicttoxml


def convert_excel_to_csv(local_input_file_name):
    input_df = pd.read_excel(local_input_file_name, sheet_name="Vehicles", dtype=str)
    number_of_lines = len(input_df.index)
    result_file_name = local_input_file_name.replace(".xlsx", ".csv")
    input_df.to_csv(result_file_name, index=None)
    if number_of_lines == 1:
        print("1 line was added to " + result_file_name)
    else:
        print(str(number_of_lines) + " lines were added to " + result_file_name)
    return result_file_name


def convert_s3db_to_csv(local_input_file_name):
    conn = sqlite3.connect(local_input_file_name)

    db_df = pandas.read_sql("SELECT * FROM convoy;", conn)
    local_output_file_name = local_input_file_name.replace(".s3db", "[CHECKED].csv")
    db_df.to_csv(local_output_file_name, index=False)


def convert_s3db_to_json(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    db_df = pandas.read_sql("SELECT * FROM convoy;", conn)
    json_output_file_name = db_name.replace(".s3db", ".json")
    xml_output_file_name = db_name.replace(".s3db", ".xml")
    db_df.to_json(json_output_file_name, orient="records")

    with open(json_output_file_name, "r") as json_file:
        result_dict = {"convoy": json.load(json_file)}
    with open(json_output_file_name, "w") as json_file:
        json.dump(result_dict, json_file)

    # create xml file from dict
    with open(xml_output_file_name, "w") as xml_file:
        xml = dicttoxml.dicttoxml(result_dict, root="", item_func=lambda item: "vehicle", attr_type=False)
        xml_file.write(xml.decode("UTF-8"))

    if len(db_df.index) == 1:
        print("1 vehicle was saved into " + json_output_file_name)
        print("1 vehicle was saved into " + xml_output_file_name)
    else:
        print(str(len(db_df.index)) + " vehicles were saved into " + json_output_file_name)
        print(str(len(db_df.index)) + " vehicles were saved into " + xml_output_file_name)

    cursor.close()
    conn.close()


def generate_scoring_files(db_name):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    json_data = []
    xml_data = []
    json_output_file_name = db_name.replace(".s3db", ".json")
    xml_output_file_name = db_name.replace(".s3db", ".xml")

    db_df = pandas.read_sql("SELECT * FROM convoy;", conn)
    json_output_file_name = db_name.replace(".s3db", ".json")
    xml_output_file_name = db_name.replace(".s3db", ".xml")

    count_json = 0
    count_xml = 0
    for index, row in db_df.iterrows():
        if row["score"] > 3:
            row.drop("score", inplace=True)
            json_data.append(row.to_dict())
            count_json += 1
        else:
            row.drop("score", inplace=True)
            xml_data.append(row.to_dict())
            count_xml += 1
    cursor.close()
    conn.close()

    with open(json_output_file_name, "w") as json_file:
        json_data = {"convoy": json_data}
        json.dump(json_data, json_file)

    # create xml file from dict
    with open(xml_output_file_name, "w") as xml_file:
        xml_data = {"convoy": xml_data}
        xml = dicttoxml.dicttoxml(xml_data, root="", item_func=lambda item: "vehicle", attr_type=False)
        xml_file.write(xml.decode("UTF-8"))

    if count_json == 1:
        print("1 vehicle was saved into " + json_output_file_name)
    else:
        print(str(count_json) + " vehicles were saved into " + json_output_file_name)

    if count_xml == 1:
        print("1 vehicle was saved into " + xml_output_file_name)
    else:
        print(str(count_xml) + " vehicles were saved into " + xml_output_file_name)


def calculate_points(row):
    route = 450  # total length of route traveled in km
    points = 0
    total_fuel_consumption = int(row["fuel_consumption"]) * (route / 100)
    if total_fuel_consumption <= 230:
        points += 2
    else:
        points += 1
    number_of_pittstops = total_fuel_consumption / int(row["engine_capacity"])

    if number_of_pittstops < 1:
        points += 2
    elif number_of_pittstops < 2:
        points += 1

    points += 2 if int(row["maximum_load"]) >= 20 else 0
    return points


def create_database(checked_csv_name):
    json_lines = []
    xml_lines = []
    db_name = checked_csv_name.replace("[CHECKED].csv", ".s3db")
    json_name = db_name.replace(".s3db", ".json")
    xml_name = db_name.replace(".s3db", ".xml")
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    result = cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = 'convoy';").fetchone()

    if not result:
        cursor.execute(
            "CREATE TABLE convoy ( vehicle_id INT PRIMARY KEY, engine_capacity INT NOT NULL, fuel_consumption INT NOT NULL, maximum_load INT NOT NULL, score INT NOT NULL );")

    with open(checked_csv_name) as csvfile:

        # create DB entries
        csvfile.seek(0)
        dict_reader = csv.DictReader(csvfile)
        records = 0
        for csv_row in dict_reader:
            json_lines.append(csv_row)
            xml_lines.append({"vehicle": csv_row})

            csv_row["points"] = calculate_points(csv_row)

            statement = "INSERT INTO convoy (vehicle_id, engine_capacity, fuel_consumption, maximum_load, score) VALUES ( {id}, {capacity}, {fuel}, {load}, {points} );".format(
                id=csv_row["vehicle_id"],
                capacity=csv_row["engine_capacity"],
                fuel=csv_row["fuel_consumption"], load=csv_row["maximum_load"], points=csv_row["points"])

            try:
                cursor.execute(statement)
            except sqlite3.IntegrityError:
                pass

            conn.commit()
            records = records + 1
    cursor.close()
    conn.close()

    if records == 1:
        print("1 record was inserted into " + db_name)
    #  print("1 vehicle was saved into " + json_name)
    #  print("1 vehicle was saved into " + xml_name)
    else:
        print(str(records) + " records were inserted into " + db_name)
    #  print(str(records) + " vehicles were saved into " + json_name)
    #  print(str(records) + " vehicles were saved into " + xml_name)

    return db_name

    convert_s3db_to_json()
    # # create json file from dict
    # dict_from_csv_json = {"convoy": json_lines}
    # with open(json_name, "w") as json_file:
    #     json.dump(dict_from_csv_json, json_file)
    # # create xml file from dict
    # with open(xml_name, "w") as xml_file:
    #     xml = dicttoxml.dicttoxml(dict_from_csv_json, root="", attr_type=False, item_func=lambda name: "vehicle")
    #     xml_file.write(xml.decode("UTF-8"))


def create_checked_csv(csv_name):
    input_df = pd.read_csv(csv_name, dtype=str)
    result_df = pandas.DataFrame(columns=input_df.columns)
    count = 0
    for index, row in input_df.iterrows():
        for entry in row:
            if re.search(r"\D", entry):
                count = count + 1

        row = row.str.replace(r"\D", "", regex=True)
        result_df = result_df.append(row)
    output_file_name = csv_name.replace(".csv", "") + "[CHECKED]" + ".csv"
    print(str(count) + " cells were corrected in " + output_file_name)
    result_df.to_csv(output_file_name, index=False, header=True)
    return output_file_name


def main():
    print("Input file name")
    input_file_name = input()

    if input_file_name.endswith(".xlsx"):
        csv_name = convert_excel_to_csv(input_file_name)
        checked_csv_name = create_checked_csv(csv_name)
        db_name = create_database(checked_csv_name)
        generate_scoring_files(db_name)

    elif input_file_name.endswith(".s3db"):
        generate_scoring_files(input_file_name)

    elif input_file_name.endswith("[CHECKED].csv"):
        db_name = create_database(input_file_name)
        generate_scoring_files(db_name)
    elif input_file_name.endswith(".csv"):
        checked_csv_name = create_checked_csv(input_file_name)
        db_name = create_database(checked_csv_name)
        generate_scoring_files(db_name)


if __name__ == '__main__':
    main()
