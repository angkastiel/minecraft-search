# -*- coding: utf-8 -*-

import sys
import os
import xml.etree.ElementTree as ET
import argparse
import subprocess
 
parser = argparse.ArgumentParser(description="Just an example",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--nbt2xml", action="store_true", help="build xml cache")
parser.add_argument("--search-players", type=str, help="search players uuids in world")
parser.add_argument("--search-ent", type=str, help="search entities in world")
parser.add_argument("--search-item", type=str, help="search items in world")
parser.add_argument("--search-res-filter", type=str, help="define fields of item or entity included in result")
parser.add_argument("--search-res-raw-uuid", action="store_true", help="define fields of item or entity included in result")
parser.add_argument("-w", "--world", type=str, help="path to world directory")
parser.add_argument("-i", "--ignore-dirs", type=str, help="list of ignored subdirectories")
parser.add_argument("--use-xml-cache", action="store_true", help="use xml cache")
args = parser.parse_args()
config = vars(args)
#print(config)


worlddir = config['world']
utildir = os.path.join(os.path.dirname(__file__), 'nbtutil')
ignoredirs = []#['region', 'poi', 'DIM-1\\region', 'DIM-1\\poi']
if ('ignore_dirs' in config):
    ignoredirs = str(config['ignore_dirs']).split(',')
extensions = ('.dat', '.dat_old', '.mca', '.mcr', '.nbt', '.schematic', '.dat_mcr', '.bpt', '.rc')
search_result_file = 'mcft-search-result.json'


def remove_file(filename):
    try:
        os.remove(filename)
    except FileNotFoundError:
        pass

def nbt2xmlfile(nbtfile, xmlfile):
    exefile = os.path.join(utildir, 'NBTUtil.exe')
    cmdline = exefile + ' --xml="' + xmlfile + '" --path="' + nbtfile + '"'
    #print(cmdline)
    remove_file(xmlfile)
    try:
       os.makedirs(os.path.dirname(xmlfile))
    except FileExistsError:
       pass
    result = subprocess.run(cmdline, shell=True)
    if ((result.returncode != 0) or (not os.path.exists(xmlfile))):
        return False
    return True
    

def build_xml_cache():
    for root, dirs, files in os.walk(worlddir):
        for file in files:
            filedir = os.path.relpath(root, worlddir)
            if (filedir in ignoredirs):
                continue
            if file.lower().endswith(extensions):
                fn = os.path.normpath(os.path.join(root, file))
                print('process file:', fn)
                try:    
                    if (not nbt2xmlfile(fn, os.path.join(worlddir, 'nbt-xml', filedir, file + '.xml'))):
                        print('not parsed')                            
                except Exception as err:
                    print('error:')
                    print(type(err))
                    print(err)

print('world dir: ', worlddir)
print('ignore subdirs: ', ignoredirs)
print('search in files: ', extensions)

if (config['nbt2xml']):
    build_xml_cache()
    sys.exit(0)

target_players = {}
target_uuids = []
if (not config['search_players'] is None):
    for s in config['search_players'].split(','):
        uuid = None
        username = None
        l = s.split(':')
        if (len(l) > 0):
            uuid = l[0]
        if (len(l) > 1):
            username = l[1]
        target_players[uuid] = username
        target_uuids.append(uuid)
    print('search players:', target_players)
         

def read_xml(filename):
    tree = ET.parse(filename)
    return tree.getroot()

def nbt2xml(filename):
    outfile = os.path.join(utildir, 'nbt2xml.result.' + str(os.getpid()) + '.xml')
    
    usecache = config['use_xml_cache']
    if (usecache):
        xmlfile = os.path.relpath(filename, worlddir) + '.xml'
        xmlfile = os.path.join(worlddir, 'nbt-xml', xmlfile)
        if (os.path.exists(xmlfile)):
            return read_xml(xmlfile) 
        outfile = xmlfile
    try:
        if (not nbt2xmlfile(filename, outfile)):
            print('nbt2xml error')
            return None
        return read_xml(outfile)
    finally:
        if (not usecache):
            remove_file(outfile)
    
def get_xml_path_part(xml):
    result = xml.tag + '[type=' + xml.attrib['type'] 
    if 'name' in xml.attrib:
        result = result + ',name=' + xml.attrib['name']
    result = result + ']'
    return result
    
def make_xml_path(chain):
    result = ""
    for xml in chain:
        result = result + get_xml_path_part(xml) + '/'
    return result
   
def merge_results(results, res):
    if (results is None):
        return res
    l = []
    if (type(results) is list):
        l.extend(results)
    else:
        l.append(results)
    if (type(res) is list):
        l.extend(res)
    else:
        l.append(res)
    return l
    
def get_name(xml):
    if ('name' in xml.attrib):
        return str(xml.attrib['name'])
    else:
        return ''
    
def get_type(xml):
    if ('type' in xml.attrib):
        return str(xml.attrib['type'])
    else:
        return ''

def get_value(xml):
    x = xml.find('v')
    if (x is None):
        x = xml.find('i')
    if (not x is None):
        return str(x.text)
    else:
        return ''
    
def get_uuid_value(xml):
    x = xml.find('v-uuid')
    if (not x is None):
        return str(x.text)
    else:
        return ''
    
def find_details(parents):
    r = []
    x = parents[len(parents)-2]
    if (get_type(x) == 'C'):
        return process_C(x, True)
    for i in x:
        n = get_name(i)
        v = process_CLV(i)
        if (n != ''):
            if should_be_field_in_result(n):
                r.append({n: v})
        else:
            r.append(v)
                
    #print(ET.tostring(x))
    return r
    
def should_be_field_in_result(field: str):
    #'search-res-filter'
    if (not 'search_res_filter' in config):
        return True
    f = config['search_res_filter']
    if (f.strip() == ''):
        f = None
    if (f is None):
        return True
    return field in f.split(',')


def find_in_C(x, field: str):
    if (get_type(x) == 'C'):
        for i in x:
            n = get_name(i)
            if (n == field):
                return i
    return None

def is_minecraft_id(s: str, ids: list):
    prefix = 'minecraft:'
    return (s.startswith(prefix) and ((s[len(prefix):] in ids) or ('*' in ids)))

def is_ent(x, ent: list) -> bool:
    i = find_in_C(x, 'id')
    if (not i is None):
        v = get_value(i)
        if (is_minecraft_id(v, ent)):
            return True
    return False

def process_C(x, apply_filter = False):
    r = {}
    for i in x:            
        n = get_name(i)
        if (not apply_filter or should_be_field_in_result(n)):
            r[n] = process_CLV(i)
    return r

def process_L(x):
    r = []
    for i in x:            
        r.append(process_CLV(i))
    return r

def process_CLV(x):
    t = get_type(x)
    if (t == 'C'):
        return process_C(x)
    else:
        if (t == 'L'):
            return process_L(x)
        else:
            uuidv = get_uuid_value(x)
            if (uuidv != '') and not config['search_res_raw_uuid']:
                return uuidv
            else:
                return get_value(x)
        

def find_ent(xml, ent: list):
    result = []
    if ((xml.tag == 'n') and (get_type(xml) == 'L') and (get_name(xml) == 'Entities')):
        for x in xml:
            if (get_type(x) == 'C'):
                if (is_ent(x, ent)):
                    result.append(process_C(x, True))
    if (len(result) == 0):
        return None
    else:
        return result

def find_players(xml, parents):
    result = None
    if ((xml.tag == 'v-uuid') and (xml.text in target_uuids)):
            path = make_xml_path(parents)
            print('uuid found:', xml.text)    
            print(path)
            print('')
            result = {'player': target_players[xml.text], 'player-uuid': xml.text, 'path': path, 'details': find_details(parents)}
    return result


def is_item(x, items: list):
    if (not is_ent(x, ['item'])):
        return False
    i = find_in_C(x, 'Item')
    if (not i is None):
        i = find_in_C(i, 'id')
        if (not i is None) and is_minecraft_id(get_value(i), items):
            return True
    return False


def find_item(xml, items: list):
    result = []
    if ((xml.tag == 'n') and (get_type(xml) == 'L') and (get_name(xml) == 'Entities')):
        for x in xml:
            if (get_type(x) == 'C'):
                if (is_item(x, items)):
                    result.append(process_C(x, True))
    if (len(result) == 0):
        return None
    else:
        return result
 
def process_search(xml, parents: list):
    do_find_ent = False
    if ('search_ent' in config):
        if (not config['search_ent'] is None):
            do_find_ent = True
    
    do_find_item = False
    if ('search_item' in config):
        if (not config['search_item'] is None):
            do_find_item = True
            
    if (do_find_ent):
        return find_ent(xml, str(config['search_ent']).split(','))
    else:
        if (do_find_item):
            return find_item(xml, str(config['search_item']).split(','))
        else:
            return find_players(xml, parents)
    return None
        

def process_xml(xml, parents: list):
    result = process_search(xml, parents)
    new_path = []
    new_path.extend(parents)
    new_path.append(xml)
    for child in xml:
        r = process_xml(child, new_path)
        if (not r is None):
            result = merge_results(result, r)
    return result
 
search_result = []
for root, dirs, files in os.walk(worlddir):
    for file in files:
        filedir = os.path.relpath(root, worlddir)
        if (filedir in ignoredirs):
            continue
        if file.lower().endswith(extensions):
            fn = os.path.normpath(os.path.join(root, file))
            print('scan file:', fn)
            try:    
                xml = nbt2xml(fn)
                if (xml is None):
                    print('not parsed')
                else:
                    r = process_xml(xml, [])
                    if (not r is None):
                        r = {'file': fn, 'result': r}
                        search_result.append(r)
                        
            except Exception as err:
                print('error:')
                print(type(err))
                print(err)
                
import json
filename = os.path.join(worlddir, search_result_file)
with open(filename, 'w') as f:
    json.dump(search_result, f, indent='    ')
print('saved to ' + filename)
