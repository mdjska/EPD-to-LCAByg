from unittest import result
import requests
import json
import click
from nested_lookup import nested_lookup, get_occurrences_and_values
from ndicts.ndicts import DataDict, NestedDict
import pandas as pd
import xmltodict
from pprint import pprint
try:
    from termcolor import colored
except ImportError:
    colored = None


def convert_to_lcabyg(process_json, uri, my_header):
    print("converting")
    indicators, _ = pprint_indicators(process_json)
    print(indicators)
    with open('lcabygJSON_templates/Stage.json', 'r') as f:
        stage = json.load(f)
    with open('lcabygJSON_templates/Product.json', 'r') as f:
        product = json.load(f)
    with open('lcabygJSON_templates/ProductToStage.json', 'r') as f:
        product_to_stage = json.load(f)
    print(type(stage))


    print("\n", "#"*24)
    stage[0]["Node"]["Stage"]["id"] = process_json["processInformation"]["dataSetInformation"]["UUID"]
    # try:
    #     name = [i for i in process_json["processInformation"]["dataSetInformation"]["name"]["baseName"] if i["lang"]=="en"][0]["value"]
    # except KeyError or IndexError:
    #     pass
    name = process_json["processInformation"]["dataSetInformation"]["name"]["baseName"][0]["value"]
    stage[0]["Node"]["Stage"]["name"]["English"] = str(name)
    stage[0]["Node"]["Stage"]["name"]["Danish"] = str(name) + "_1"
    stage[0]["Node"]["Stage"]["comment"] = process_json["processInformation"]["dataSetInformation"]["generalComment"][0]["value"]
    valid_to = process_json["processInformation"]["time"]["dataSetValidUntil"]
    if len(str(valid_to)) == 4 and str(valid_to).isdigit():
        valid_to = str(valid_to) + "-01-01"
    stage[0]["Node"]["Stage"]["valid_to"] = valid_to
    referenceToReferenceFlow = process_json["processInformation"]["quantitativeReference"]["referenceToReferenceFlow"][0]
    referenceToFlowDataSet = [i for i in process_json["exchanges"]["exchange"] if i["dataSetInternalID"]==referenceToReferenceFlow]
    try:
        flowProperties = [i for i in referenceToFlowDataSet[0]["flowProperties"] if "referenceUnit" in i]
        if flowProperties:
            referenceUnit = flowProperties[0]["referenceUnit"]
        else:
            raise KeyError
    except KeyError:
        try:
            flowProperties_unitgroup = referenceToFlowDataSet[0]["flowProperties"][0]["uuid"]
            unit_uri = uri.split("processes")[0] + "unitgroups/" + flowProperties_unitgroup
            flow_params = {"format": "JSON"}
            if "oekobaudat" in unit_uri:
                print("Hello oekobaudat")
                response = requests.get(
                    unit_uri, params=flow_params
                )
            else:
                response = requests.get(
                unit_uri, params=flow_params, headers=my_header
            )
                print(response)
            unitGroup = json.loads(response.text)
            print(json.dumps(unitGroup, indent=4))
            referenceToReferenceUnit = unitGroup["unitGroupInformation"]["quantitativeReference"]["referenceToReferenceUnit"]
            referenceUnit = unitGroup["units"]["unit"][referenceToReferenceUnit]["name"]
        except Exception as e:
            print(e)
            print(colored("Couldn't find 'Reference Unit'", "red"))
    if referenceUnit in ["qm", "QM"]:
        referenceUnit = "M2"
    if referenceUnit in ["pcs", "pcs.", "PCS", "PCS."]:
        referenceUnit = "STK"
    accepted_units = ["KG", "M", "M2", "M3", "STK", "L", "TON"]
    if referenceUnit.upper() not in accepted_units:
        referenceUnit = click.prompt(
        colored(f"Cannot match unit. Found unit: {referenceUnit.upper()}. Which of the accepted units does it match?", 'red'),
        type=click.Choice(accepted_units, case_sensitive=False),
        show_choices=True
    )
        print(colored(f"You chose {referenceUnit.upper()}.", 'green'))
    stage[0]["Node"]["Stage"]["stage_unit"] = referenceUnit.upper()
    stage[0]["Node"]["Stage"]["indicator_unit"] = referenceUnit.upper()

    meanValue = referenceToFlowDataSet[0]["flowProperties"][0]["meanValue"]
    stage[0]["Node"]["Stage"]["stage_factor"] = meanValue
    stage[0]["Node"]["Stage"]["indicator_factor"] = meanValue
    stage[0]["Node"]["Stage"]["external_source"] = process_json["administrativeInformation"]["dataEntryBy"]["referenceToDataSetFormat"][0]["shortDescription"][0]["value"]
    stage[0]["Node"]["Stage"]["external_id"] = process_json["processInformation"]["dataSetInformation"]["UUID"]
    stage[0]["Node"]["Stage"]["external_version"] = process_json["administrativeInformation"]["publicationAndOwnership"]["dataSetVersion"]
    stage[0]["Node"]["Stage"]["external_url"] = uri
    data_type = [i for i in process_json["modellingAndValidation"]["LCIMethodAndAllocation"]["other"]["anies"] if i["name"]=="subType"]
    data_type = data_type[0]["value"].lower()
    accepted_data_types = ["Generic", "Specific", "Skabelon", "Repræsentativt", "Gennemsnitligt"]
    if "specific" in data_type:
        data_type = "Specific"
    elif "generic" in data_type:
        data_type = "Generic"
    elif "average" in data_type:
        data_type = "Gennemsnitligt"
    elif "representative" in data_type:
        data_type = "Repræsentativt"
    elif "template" in data_type:
        data_type = "Skabelon"
    else:
        data_type_index = click.prompt(
        colored(f'Cannot match dataset type. Found dataset type: {data_type}. Which of the accepted dataset types does it match? \n{accepted_data_types}', 'red'),
        type=click.Choice(["0", "1", "2", "3", "4"]),
        show_choices=True
    )
        data_type = accepted_data_types[int(data_type_index)]
        print(colored(f"You chose {data_type}.", 'green'))
    stage[0]["Node"]["Stage"]["data_type"] = data_type
    # indicators, _ = pprint_indicators(process_json)

    for indicator in stage[0]["Node"]["Stage"]["indicators"]:
        if indicator in indicators:
            stage[0]["Node"]["Stage"]["indicators"][f"{indicator}"] = indicators[indicator]["Total"][0]
    print(json.dumps(stage, indent=4))
    # result_json_file = open("stage_test.json", "w")
    # result_json_file.write(json.dumps(stage, ensure_ascii=False, indent=4))
    filename = "Stage"
    return stage, name

def pprint_indicators(process_json, module_flag=False):
    
    indicators = {}
    lines = []
    for obj in process_json["LCIAResults"]["LCIAResult"]:
        indicator = {"Indicator": [], "Unit": [], "Emissions": [], "Total": []}
    
        # indicator_name = obj["referenceToLCIAMethodDataSet"]["shortDescription"][1][
        #     "value"
        # ]
        indicator_name = obj["referenceToLCIAMethodDataSet"]["shortDescription"][0][
            "value"
        ]
        unit_dict = [i for i in obj["other"]["anies"] if "name" in i]
        unit = unit_dict[0]["value"]["shortDescription"][0]["value"]
        line = click.style("#" * 60, fg='cyan')
        title = click.style(f"Indicator: {indicator_name}\nUnit: {unit} \n \nEmissions: ", fg='cyan', bold=True)
        lines.append(line+"\n\n"+title)
        emission_total = 0
        emissions = [i for i in obj["other"]["anies"] if "module" in i]
        for emission in emissions:
            emission_total += float(emission["value"])
            if module_flag == 'y':
                lines.append(f"\n\tModule: {emission['module']}\n\tValue: {float(emission['value'])}")
                try:
                    lines.append(f"\tScenario: {emission['scenario']}")
                except KeyError:
                    continue

        total = f"Total: {round(emission_total, 4)} {unit}"
        lines.append("\n"+click.style(str(total)+"\n", fg='cyan', bold=True))
        indicator["Indicator"].append(f"{indicator_name}")
        indicator["Unit"].append(f"{unit}")
        indicator["Emissions"].append(emissions)
        indicator["Total"].append(f"{emission_total}")
        name_code = indicator_name.rstrip("*")[indicator_name.rfind("(") + 1: -1]

        indicators[f"{name_code}"] = indicator

    return indicators, lines