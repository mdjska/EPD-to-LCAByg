#!/usr/bin/env python3
import re
import os
import pathlib
from socket import NI_NAMEREQD
import click
import requests
from pyfiglet import Figlet, figlet_format
import json
try:
    from termcolor import colored
except ImportError:
    colored = None
from epd_data import pprint_indicators, convert_to_lcabyg

base_urls = {
                "ECOPLATFORM" : "https://data.eco-platform.org/resource/",
                "ECOSMDP": "https://ecosmdp.eco-platform.org/resource/",
                "IBU_DATA" : "https://ibudata.lca-data.com/resource/",
                "EPD-NORWAY_DIGI" : "https://epdnorway.lca-data.com/resource/",
                "ENVIRONDEC": "https://data.environdec.com/resource/",
                "EPD_ITALY" : "https://node.epditaly.it/Node/resource/",
                "MRPI": "https://data.mrpi.nl/resource/",
                "EPD_IRELAND": "https://epdireland.lca-data.com/resource/",
                "ITBPOLAND": "https://itb.lca-data.com/resource/",
                "BRE_EPD_Hub": "https://soda4lca.bregroup.com/resource/",
                "OEOKOBAUDAT" : "https://oekobaudat.de/OEKOBAU.DAT/resource/datastocks/cd2bda71-760b-4fcc-8a0b-3877c10000a8/"
                }

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])

class ApiKey(click.ParamType):
    name = 'api-key'

    def convert(self, value, param, ctx):
        found = re.match("^[-._A-Za-z0-9]*$", value)
        if not found:
            self.fail(
                f"Your API Token should only contain lettes, numbers and ('.','-','_'). You provided: {value}",
                param,
                ctx,
            )

        return value

def display_title_bar():
    # Clears the terminal screen, and displays a title bar.
    os.system('clear')
    f = Figlet(font='slant')

    print(colored("*", 'cyan') * 75)
    print(colored(f.renderText('EPD to LCAByg'), 'cyan'))
    print(colored("*", 'cyan') * 75)

def get_user_choice_node(base_urls):
    for i, name in enumerate(base_urls):
        print(f"[{i}] \t {name}")
    print("[q] Quit.")
    choice = click.prompt(
        "Where does your UUID come from?",
        type=int
    )
    if choice == "q":
        print("Goodbye")
        return
    else:
        choice = list(base_urls.keys())[choice]
    return choice

def show_overview(json_result):
    results = []
    print("#"*40, "OVERVIEW", "#"*40)
    for i, result in enumerate(json_result["data"]):
        name = result["name"]
        nodeid = result["nodeid"]
        tab = "\t"
        print(f'[{i}] {tab} {"RESULT"} {i} {tab} {"Node: "}{nodeid}{"  "} {tab} {"Name: "}"{name}"')
        results.append(result)
    print("[q] Quit.")
    print("#"*90, "\n")
    return results

def get_incremental_path(epd_name):
    default_path = f'{epd_name}.json'
    default_path = re.sub('[^a-zA-Z0-9 \n\.]', '', default_path).replace(' ', '_')
    full_path = os.path.join(os.getcwd(), default_path)
    path = click.prompt(
    "Path: ",
    type=click.Path(dir_okay=True, writable=True, path_type=pathlib.Path),
    default= full_path,
    )
    if not pathlib.Path(path).suffix == '.json':
        print(colored("Seems like you're missing a JSON file extention. Add '.json' at the end of your path.", 'red'))
        get_incremental_path(epd_name)
    if path.is_dir():
        path = pathlib.Path.joinpath(path, default_path)
    if os.path.exists(path):
        i = 1
        while os.path.exists(f"{str(path).split('.')[:-1][0]}_{i}.{str(path).split('.')[-1]}"):
            i += 1
        path_incr = os.path.join(os.getcwd(), f"{str(path).split('.')[:-1][0]}_{i}.{str(path).split('.')[-1]}")
        save = click.prompt(colored(f'File with name: "{path}" already exists. \nDo you want to save file as "{path_incr}"?', "red"), type=click.Choice(['y', 'n']), default = 'y')
        if save == 'y':
            path = path_incr
        elif save == 'n':
            get_incremental_path(epd_name)
    return path


def process_info(nodeid, uuid, my_header, pprint=False):
    choice_url = base_urls[nodeid] + "processes/" + uuid
    request_params_process = {"format": "json", "view": "extended"}
    response = requests.get(
        choice_url, params=request_params_process, headers=my_header
    )
    process_json = json.loads(response.text)

    if pprint:
        module_flag = click.prompt(
        "Show indicators pr. module?",
        type=click.Choice(['y', 'n']),
        default='n'
        )
        pprint_indicators(process_json, module_flag=module_flag)

    return process_json

def save_to_file(process_json, name=None):

    if not name:
        name = process_json["processInformation"]["dataSetInformation"]["name"]["baseName"][0]["value"]
        #print(colored(f"\nYour EPD's name is: {name}\n", "green"))
    incremental_path = get_incremental_path(name)
    with open(incremental_path, "x") as f:
        f.write(json.dumps(process_json, indent=4))
    print(colored(f'\nFile was saved to "{incremental_path}"', "green"))
    return


def back(my_header, json_result=None, nodeid=None, uuid=None, search_flag=False):
    choice_back = click.prompt(
            "Go back?",
            type=click.Choice(['y','q']),
            default='y'
        )
    if choice_back == "y":
        info_or_convert(my_header, json_result=json_result, nodeid=nodeid, uuid=uuid, search_flag=search_flag)
    if choice_back == "q":
        print("Goodbye")
        exit()
    return

def info_or_convert(my_header,search_flag, json_result=None, nodeid=None, uuid=None):
    if search_flag:
        results = show_overview(json_result)
    choice_ICS = click.prompt(
        "Get more info[i], convert[c] to LCAByg JSON or save[s] process to file?",
        type=click.Choice(['i', 'c', 's', 'q']),
        default='C'
    )
    if choice_ICS == "q":
        print("Goodbye")
        exit()
    if search_flag:
        choices = [str(i) for i in range(len(results))]
        choices.append("q")
        choice = click.prompt(
                "Pick result",
                type=click.Choice(choices),
                show_choices=False
            )
        if choice == "q":
            print("Goodbye")
            exit()
        choice = results[int(choice)]
        nodeid = choice["nodeid"]
        uuid = choice["uuid"]
        name = choice["name"]
    
    if choice_ICS == "i":
        process_info(nodeid, uuid, my_header, pprint=True)
        back(my_header, json_result=json_result, nodeid=nodeid, uuid=uuid, search_flag=search_flag)
    elif choice_ICS == "c":
        process_json = process_info(nodeid, uuid, my_header, pprint=False)
        convert_to_lcabyg(process_json)
        back(my_header, json_result=json_result, nodeid=nodeid, uuid=uuid, search_flag=search_flag)
    elif choice_ICS == "s":
        process_json = process_info(nodeid, uuid, my_header, pprint=False)
        save_to_file(process_json)
        back(my_header, json_result=json_result, nodeid=nodeid, uuid=uuid, search_flag=search_flag)
    return choice

def get_node_origin():
    print("#"*40, "Node List", "#"*40)
    for i, node in enumerate(list(base_urls)):
        tab = "\t"
        print(f'[{i}] {tab} {node}')
    print("[q] Quit.")
    print("#"*90, "\n")
    choices = [str(i) for i in range(len(list(base_urls)))]
    choices.append("q")

    node_choice = click.prompt(
        "Which node does the UUID come from?",
        type=click.Choice(choices),
        show_choices=False
    )
    if node_choice == "q":
        print("Goodbye")
        exit()
    node_choice = list(base_urls)[int(node_choice)]
    return node_choice

def search_EPDs(api_key, params, okobau, search_keyword):

    my_header = {"Authorization": "Bearer " + api_key}

    # NODE BASE URLs
    # base_url = get_user_choice_node(base_urls)
    request_params = {
                "search": "true",
                "metaDataOnly": "false",
                "distributed": "true",
                "virtual": "true",
                "format": "JSON",
                "view": "extended",
            }
    params = {"name": "plaster","pageSize": "10"}
    request_params.update(params)
    print("search_keyword: ", search_keyword)
    if search_keyword:
        request_params["name"] = search_keyword
    if okobau:
        process_url = base_urls["OEOKOBAUDAT"] + "processes/"
        response = requests.get(
        process_url, params=request_params)
    else:
        process_url = base_urls["ECOPLATFORM"] + "processes/"
        response = requests.get(
            process_url, params=request_params, headers=my_header
        )
    json_result = json.loads(response.text)
    # json_result = json.dumps(json_result, indent=4)

    for i, result in enumerate(json_result["data"]):
        print("#"*24, f"RESULT {i}", "#"*24)
        print(json.dumps(result, indent=4))

    # get_more_info = click.prompt(
    #     "Get more info?",
    #     type=click.Choice(['y', 'n']),
    #     default='n'
    # )
    # if get_more_info == "y":
    info_or_convert(my_header, json_result=json_result, search_flag=True)
    
    return


@click.group(context_settings=CONTEXT_SETTINGS)
@click.option(
    '--api-key', '-a',
    type=ApiKey(),
    help='Your API key for ECO Platform',
)
@click.option(
    '--config-file', '-c',
    type=click.Path(),
    default='~/.ecoportal_api_key.cfg',
    help="Path for saving API key config file"
)
@click.pass_context
def main(ctx, api_key, config_file):
    """
    A little tool that converts EPDs from either ECO PORTAL or OKOBAUDAT to LCAByg compatible JSON files.
    You can either:

        1. Search for an EPD on ECO PORTAL or OKOBAUDAT.

        2. Provide a valid UUID for an EPD from one of these platforms.\n
    You need a valid API key from ECO Platform for the tool to work. You can
    sign up for a free account at https://data.eco-platform.org/registration.xhtml.
    """
    filename = os.path.expanduser(config_file)
    if not api_key and os.path.exists(filename):
        with open(filename) as cfg:
            api_key = cfg.read()
    
    choice = ''
    display_title_bar()
    # while choice != 'q':    
        
    #     choice = get_user_choice()
        
    #     # Respond to the user's choice.
    #     display_title_bar()

    ctx.obj = {
        'api_key': api_key,
        'config_file': filename,
    }


@main.command()
@click.pass_context
def config(ctx):
    """
    Store configuration values in a file, e.g. the API key for Eco PORTAL.
    """
    config_file = ctx.obj['config_file']
    api_key = click.prompt(
        "Please enter your API key. Click 'Enter' to pick saved API key",
        default=ctx.obj.get('api_key', ''),
        show_default=False,
        type=ApiKey()
    )

    with open(config_file, 'w') as cfg:
        cfg.write(api_key)
        print(f"API key saved to {config_file}")



@main.command()
@click.option(
    '--okobau', '-o',
    is_flag = True,
    default=False,
    show_default = True,
    help='Set flag if you want to search OKOBAUDAT. ECO Platform is the default.',
)
@click.option(
    '--params', '-p',
    type=dict,
    help='Search parameters as a dict. \n"name" is the search term.\n"pagesize" is the number of (top) results returned.',
    default = {"name": "plaster", "sortBy": "referenceYear","sortOrder": "false","pageSize": "10","location": "RER"},
    show_default = True,
    )
@click.option(
    "--search-keyword", "-k",
    type=str,
    help="search keyword"
)
@click.pass_context
def search(ctx, okobau, params, search_keyword):
    """
    Search for EPDs. Save it as a LCAByg compatible JSON file.
    """
    api_key = ctx.obj['api_key']
    #if not (okobau, params, search_keyword):
        
    response = search_EPDs(api_key, params, okobau, search_keyword)
    print(f"Response: {response}.")

@main.command()
@click.argument('UUID')
@click.pass_context
def existing(ctx, uuid):
    """
    Provide an EPD UUID and generate an LCAByg compatible JSON file for it.
    """
    api_key = ctx.obj['api_key']

    print(colored(f"\nThe existing UUID is {uuid}.", "green"))
    nodeid = get_node_origin()
    api_key = ctx.obj['api_key']
    my_header = {"Authorization": "Bearer " + api_key}
    info_or_convert(my_header, search_flag=False, nodeid=nodeid, uuid=uuid)


if __name__ == "__main__":
    main()
