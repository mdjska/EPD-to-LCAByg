#!/usr/bin/env python3
from random import choices
from pydoc import pager
import re
import os
import pathlib
from pathlib import Path
import readline
from socket import NI_NAMEREQD
from typing_extensions import Required
import click
import requests
from pyfiglet import Figlet, figlet_format
from appdirs import AppDirs
# import colorama
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
                "OEKOBAU.DAT" : "https://oekobaudat.de/OEKOBAU.DAT/resource/datastocks/cd2bda71-760b-4fcc-8a0b-3877c10000a8/"
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
    # click.clear
    f = Figlet(font='slant')

    # while True:
    #     print('\33[2J')
    click.clear()
    click.secho("*"* 75, fg='cyan')
    click.secho(f.renderText('EPD to LCAByg'), fg='cyan')
    click.secho("*"* 75, fg='cyan')

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
    title = "#"*40 + " OVERVIEW "+ "#"*40
    click.secho(title, fg="cyan")
    for i, result in enumerate(json_result["data"]):
        if "name" in result:
            name = result["name"]
        else:
            name = "None"
        nodeid = result["nodeid"]
        tab = "\t"
        print(f'[{i}] {tab} {"RESULT"} {i} {tab} {"Node: "}{nodeid}{"  "} {tab} {"Name: "}"{name}"')
        results.append(result)
    print("[q] Quit.")
    line = "#"*90
    click.secho(line, fg="cyan")
    return results

@click.pass_context
def get_incremental_path(ctx, name, dir=False):
    default_path = f'{name}.json'
    if dir:
        default_path = name
    default_path = re.sub('[^a-zA-Z0-9 \n\.]', '', default_path).replace(' ', '_')
    full_path = os.path.join(os.getcwd(), default_path)
    if dir:
        result_folder = ctx.obj['result_folder']
        result_folder = Path(result_folder).resolve()
        full_path = Path.joinpath(result_folder, default_path)

    path = click.prompt(
    "Path: ",
    type=click.Path(dir_okay=True, writable=True, path_type=Path),
    default= full_path,
    )
    if not dir:
        if path.is_dir():
            path = Path.joinpath(path, default_path)
        if not Path(path).suffix == '.json':
            click.secho("Seems like you're missing a JSON file extention. Add '.json' at the end of your path.", fg='red')
            path = get_incremental_path(name)
    if os.path.exists(path):
        i = 1
        if not dir:
            while os.path.exists(f"{str(path).split('.')[:-1][0]}_{i}.{str(path).split('.')[-1]}"):
                i += 1
            path_incr = os.path.join(os.getcwd(), f"{str(path).split('.')[:-1][0]}_{i}.{str(path).split('.')[-1]}")
            type = "file"
        elif dir:
            while os.path.exists(f"{path}_{i}"):
                i += 1
            path_incr = pathlib.Path(f"{path}_{i}")
            print(path_incr)
            type = "folder"

        save = click.prompt(click.style(f'{type} with name: "{path}" already exists. \nDo you want to save {type} as "{path_incr}"?', fg="red"), type=click.Choice(['y', 'n']), default = 'y')
        if save == 'y':
            path = path_incr
        elif save == 'n':
            path = get_incremental_path(name, dir=dir)
    return Path(path)


def process_info(nodeid, uuid, my_header, okobau, pprint=False):
    choice_url = base_urls[nodeid] + "processes/" + uuid
    request_params_process = {"format": "json", "view": "extended"}
    try:
        if okobau:
            response = requests.get(
                choice_url, params=request_params_process
            )
        elif not okobau:
            response = requests.get(
                choice_url, params=request_params_process, headers=my_header
            )
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        if response.status_code == 403:
            click.secho("403 Forbidden: Possibly due to an invalid or expired API token.", fg="red")
        raise SystemExit(click.secho(err, fg="red"))
    process_json = json.loads(response.text)
    
    if pprint:
        module_flag = click.prompt(
            "Show indicators pr. module?",
            type=click.Choice(['y', 'n'], case_sensitive=False),
            default='n'
            )
        _, lines, _ = pprint_indicators(process_json, module_flag=module_flag)
        click.echo_via_pager("\n".join(lines), color=True)

    return process_json, choice_url


def save_to_file(process_json, name=None, stage=None, incremental_path=None, convert=False):
    if not name:
        name = process_json["processInformation"]["dataSetInformation"]["name"]["baseName"][0]["value"]
        #print(colored(f"\nYour EPD's name is: {name}\n", "green"))
    
    if not convert:
        file_path = get_incremental_path(name)
        print("######: ", file_path)
        if not file_path.parent.absolute().exists():
            file_path.parent.absolute().mkdir(parents=True)
        with open(file_path, "x") as f:
            f.write(json.dumps(process_json, ensure_ascii=False, indent=4))
    elif convert and incremental_path:
        if not os.path.exists(incremental_path):
            incremental_path.mkdir(parents=True)
        stage_path = Path.joinpath(incremental_path, stage)
        stage_path.mkdir()
        file_path = Path.joinpath(stage_path, "Stage.json")
        with open(file_path, "x") as f:
            f.write(json.dumps(process_json, ensure_ascii=False, indent=4))
    click.secho(f'File was saved to "{file_path}"', fg="green")
    return


def back(my_header, json_result=None, nodeid=None, uuid=None, search_flag=False):
    choice_back = click.prompt(
            "Go back?",
            type=click.Choice(['y','q'], case_sensitive=False),
            default='y'
        )
    if choice_back == "y":
        info_or_convert(my_header, json_result=json_result, nodeid=nodeid, uuid=uuid, search_flag=search_flag)
    if choice_back == "q":
        click.echo("Goodbye")
        exit()
    return

def info_or_convert(my_header,search_flag, json_result=None, okobau=None, nodeid=None, uuid=None):
    if search_flag:
        results = show_overview(json_result)
    choice_ICS = click.prompt(
        click.style("Get more info[i], convert[c] to LCAByg JSON or save[s] process to file?", fg = "cyan"),
        type=click.Choice(['i', 'c', 's', 'q'], case_sensitive=False),
        default='c'
    )
    if choice_ICS == "q":
        click.echo("Goodbye")
        exit()
    if search_flag:
        choices = [str(i) for i in range(len(results))]
        choices.append("q")
        choice = click.prompt(
                "Pick result",
                type=click.Choice(choices, case_sensitive=False),
                show_choices=False
            )
        if choice == "q":
            click.echo("Goodbye")
            exit()
        choice = results[int(choice)]
        nodeid = choice["nodeid"]
        uuid = choice["uuid"]
    
    if choice_ICS == "i":
        process_info(nodeid, uuid, my_header, okobau, pprint=True)
        back(my_header, json_result=json_result, nodeid=nodeid, uuid=uuid, search_flag=search_flag)
    elif choice_ICS == "c":
        process_json, uri = process_info(nodeid, uuid, my_header, okobau, pprint=False)
        stages = convert_to_lcabyg(process_json, uri, my_header, nodeid)
        incremental_path = get_incremental_path(stages[0][1], dir=True)
        for stage in stages:
            save_to_file(process_json = stage[0], name = stage[1], stage = stage[2], incremental_path=incremental_path, convert=True)
        back(my_header, json_result=json_result, nodeid=nodeid, uuid=uuid, search_flag=search_flag)
    elif choice_ICS == "s":
        process_json,_ = process_info(nodeid, uuid, my_header,okobau , pprint=False)
        save_to_file(process_json)
        back(my_header, json_result=json_result, nodeid=nodeid, uuid=uuid, search_flag=search_flag)
    return choice

def get_node_origin():
    title = "#"*40 + " Node List "+ "#"*40
    click.secho(title, fg="cyan")
    for i, node in enumerate(list(base_urls)):
        tab = "\t"
        click.echo(f'[{i}] {tab} {node}')
    click.echo("[q] Quit.")
    line = "#"*90
    click.secho(line, fg="cyan")
    choices = [str(i) for i in range(len(list(base_urls)))]
    choices.append("q")

    node_choice = click.prompt(
        "Which node does the UUID come from?",
        type=click.Choice(choices, case_sensitive=False),
        show_choices=False
    )
    if node_choice == "q":
        click.echo("Goodbye")
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
    try:
        if okobau:
            process_url = base_urls["OEKOBAU.DAT"] + "processes/"
            response = requests.get(process_url, params=request_params)
        elif not okobau:
            process_url = base_urls["ECOPLATFORM"] + "processes/"
            response = requests.get(
                process_url, params=request_params, headers=my_header
            )
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        if response.status_code == 403:
            click.secho("403 Forbidden: Possibly due to an invalid or expired API token.", fg="red")
        raise SystemExit(click.secho(err, fg="red"))
    json_result = json.loads(response.text)

    results = []
    for i, result in enumerate(json_result["data"]):
        title = "#"*24+ f" RESULT {i} "+ "#"*24
        results.append(click.style(title, fg="cyan"))
        results.append(json.dumps(result, indent=4))
    click.echo_via_pager("\n".join(results), color=True)
    click.secho("\n".join(results))

    info_or_convert(my_header, json_result=json_result, okobau=okobau, search_flag=True)
    
    return


# @click.option(
#     '--api-key', '-a',
#     type=ApiKey(),
#     help='Your API key for ECO Platform',
# )
# @click.option(
#     '--config-file', '-c',
#     type=click.Path(dir_okay=False),
#     help="Path for saving API key config file"
# )
# @click.option(
#     '--convert_folder', '-f',
#     type=click.Path(dir_okay=True, file_okay=False),
#     default='.',
#     help="Parent path for saving converted files"
# )
@click.group(context_settings=CONTEXT_SETTINGS)
@click.option(
    '--config-file', '-c',
    type=click.Path(dir_okay=False, writable=True, readable=True, file_okay=True, path_type=Path),
    help="Set a new config file path",
    prompt=True,
    prompt_required=False,
    default=Path.joinpath(Path(click.get_app_dir("EPDtoLCAByg")), Path(".config.cfg")),
)
@click.pass_context
def main(ctx, config_file):
    """
    A little tool that converts EPDs from either ECO PORTAL or OKOBAUDAT to LCAByg compatible JSON files.
    You can either:

        1. Search for an EPD on ECO PORTAL or OKOBAUDAT.

        2. Provide a valid UUID for an EPD from one of these platforms.\n
    You need a valid API key from ECO Platform for the tool to work. You can
    sign up for a free account at https://data.eco-platform.org/registration.xhtml.
    """
    display_title_bar()
    config_file = create_config(config_file)
    if os.path.exists(config_file):
        with open(config_file, "r+") as cfg:
            config = json.loads(cfg.read())
            api_key = config["api_key"]
            result_folder = config["result_folder"]
        if not api_key:
            raise SystemExit(click.secho("No API key found. Please set your API key using the 'set-api-key' command or by placing it directly in the config file.", fg="red"))
    choice = ''
    # while choice != 'q':    
        
    #     choice = get_user_choice()
        
    #     # Respond to the user's choice.

    ctx.obj = {
            'api_key': api_key,
            'config_file': config_file,
            'result_folder': result_folder
        }


# @main.command()
# @click.option(
#     '--config-file', '-c',
#     required = True,
#     type=click.Path(dir_okay=False, writable=True, readable=True, file_okay=True),
#     help="Set a new config file path",
#     prompt=True,
#     prompt_required=False,
#     default="~/.config/EPDtoLCAByg/.epd_to_lcabyg_config.cfg",
# )
# @click.confirmation_option(prompt="Setting new config file path?")
# @click.pass_context
# def set_config_file(ctx, config_file):
#     """
#     Set a new config file path. Default [~/.config/EPDtoLCAByg/.epd_to_lcabyg_config.cfg].
#     """
#     if config_file:
#         config_file = os.path.expanduser(config_file)
#         config_file = pathlib.Path(config_file).resolve()
#         print(colored(f"New config path is {config_file}.", "green"))
#         ctx.parent.obj["config_file"] = config_file
#         config_path = config_file



@main.command()
@click.pass_context
def read_config_file(ctx):
    config_file = ctx.obj['config_file']
    click.secho(f"Your config file is: {config_file}!", fg='green')


def create_config(user_config):
    config = dict.fromkeys(['api_key', 'result_folder'])
    user_config_dir = user_config.parent.absolute()
    if not user_config_dir.exists():
        user_config_dir.mkdir(parents=True)
    try:
        with open(user_config, 'r+') as cfg:
            config = json.loads(cfg.read())
            bool(('api_key', 'result_folder') in config)
    except (ValueError, KeyError, FileNotFoundError) as e:
        with open(user_config, 'w+') as cfg:
            cfg.write(json.dumps(config))
            click.secho(f"Config file created at {user_config}.", fg="green")
    return user_config


@main.command()
@click.option(
    "--api-key", "-a",
    required = True,
    type=ApiKey(),
    prompt="Please enter your API key.",
    help="Save your API key for ECO Platform",
)
@click.confirmation_option(prompt="Setting a new api key?")
@click.pass_context
def set_api_key(ctx, api_key):
    """
    Save your API key for Eco PORTAL.
    """
    config_file = ctx.obj['config_file']
    print("config_file API: ", config_file)
    with open(config_file, 'r+') as cfg:
        config = json.loads(cfg.read())
        print("READ CONFIG: ", config)
        result_folder = config['result_folder']
    with open(config_file, 'w+') as cfg:
        config["api_key"] = api_key
        cfg.write(json.dumps(config))
        click.secho(f"API key saved to {config_file}.", fg="green")

@main.command()
@click.option(
    "--result-folder", "-f",
    required = True,
    type=click.Path(dir_okay=True, file_okay=False, resolve_path=True, writable=True),
    help="Folder path for saving converted files",
    prompt="Please enter a folder path for saving converted files.",
    prompt_required=False,
    default="./converted_files/",
)
@click.confirmation_option(prompt="Setting new result folder path?")
@click.pass_context
def set_result_folder(ctx, result_folder):
    """
    Set folder path for saving converted files.
    """
    config_file = ctx.obj['config_file']
    print("config_file  result folder: ", config_file)
    with open(config_file, 'r+') as cfg:
        config = json.loads(cfg.read())
        print("READ CONFIG: ", config)
        # result_folder = config['result_folder']
    with open(config_file, 'w+') as cfg:
        config["result_folder"] = result_folder
        cfg.write(json.dumps(config))
        click.secho(f"Result folder set to {result_folder}.", fg="green")

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
