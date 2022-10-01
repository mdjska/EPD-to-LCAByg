from unittest import result
import requests
import json
from nested_lookup import nested_lookup, get_occurrences_and_values
from ndicts.ndicts import DataDict, NestedDict
import pandas as pd
import xmltodict
from pprint import pprint

def convert_to_lcabyg():
    return

def pprint_indicators(process_flow_json, module_flag=False):
    
    indicators = {}

    for obj in process_flow_json["LCIAResults"]["LCIAResult"]:
        indicator = {"Indicator": [], "Unit": [], "Emissions": [], "Total": []}
    
        # indicator_name = obj["referenceToLCIAMethodDataSet"]["shortDescription"][1][
        #     "value"
        # ]
        indicator_name = obj["referenceToLCIAMethodDataSet"]["shortDescription"][0][
            "value"
        ]
        unit_dict = [i for i in obj["other"]["anies"] if "name" in i]
        unit = unit_dict[0]["value"]["shortDescription"][0]["value"]
        print(
            "#" * 40,
            f"\n Indicator: {indicator_name}\n Unit: {unit} \n \n Emissions: ",
        )
        emission_total = 0
        emissions = [i for i in obj["other"]["anies"] if "module" in i]
        for emission in emissions:
            emission_total += float(emission["value"])
            if module_flag == 'y':
                print(f"\n  Module: {emission['module']} \n  Value: {round(float(emission['value']), 4)}")
                try:
                    print(f"  Scenario: {emission['scenario']}")
                except:
                    continue

        print(f"\n Total: {round(emission_total, 4)} {unit}\n")
        indicator["Indicator"].append(f"{indicator_name}")
        indicator["Unit"].append(f"{unit}")
        indicator["Emissions"].append(emissions)
        indicator["Total"].append(f"{emission_total}")
        name_code = indicator_name.rstrip("*")[indicator_name.rfind("(") + 1 : -1]

        indicators[f"{name_code}"] = indicator

    return indicators