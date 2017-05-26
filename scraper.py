#!/usr/local/bin/python3
from datetime import datetime, timedelta
from re import search, findall, sub
import collections
import asyncio
import aiohttp
from html.parser import HTMLParser
import csv
import pygsheets

#################
#### CLASSES ####
#################

class dataParser(HTMLParser): ##gotta have the input as an HTMLParser Object
    def __init__(self, strict):
        HTMLParser.__init__(self)
        self.dataList = []
    #appends HTML strings (sanitized except whitespaces)
    def handle_data(self, data):
        try:
            #(-) before ($) before aA1_ connected/tailed by !"#$%&'()*+,-.:
            data = search(r'[-]?[$]?[\w]+[\w -.:]*', data).group(0)
            self.dataList.append(data)
            #clean.append(temp.strip()) #strip whitespace
        except:
            pass
    def handle_starttag(self, tag, attrs):
        #appends nat & alliance link addresses to dataList
        if tag == 'a':
            for attr in attrs:
                if attr[0] == 'href':
                    try:
                        link = attr[1]
                        nat = '(\/stats\.php\?id=\d+)'
                        alliance = '(alliancestats\.php\?allianceid=\d+)'
                        link = search('{}|{}'.format(nat, alliance), link).group(0)
                        self.dataList.append(link)
                    except:
                        pass
        #use @ to filter out Description, which is sanitized in ()
        #appends @Name: keyword to dataList
        if tag == 'p':
            for attr in attrs:
                if attr[0] == 'id' and attr[1] == 'nationtitle':
                    self.dataList.append('@Name:')
        #appends @Leader: keyword to dataList
        if tag == 'img':
            for attr in attrs:
                if attr[0] == 'class' and attr[1] == 'img-polaroid':
                    self.dataList.append('@Leader:')
        #appends @Activity: keyword to dataList
        if tag == 'font':
            for attr in attrs:
                if attr[0] == 'size' and attr[1] == '2':
                    self.dataList.append('@AFK:')
class Stat():
    def __init__(self, keyword='', offset=1, value='', levels=(), valint=None):
        self.keyword = keyword # finds this stat in dataList
        self.offset = offset # stat value is this far away from keyword in List
        self.value = value # the actual value of this stat
        self.levels = levels # some stats have descriptive text instead of %
                             # this is defined in class Nation
                             # tuples = regular levels (e.g., every 10%)
                             # dicts = arbitrary levels (tech and af)
        self.valint = valint # int(value) or the appropriate int from levels

    def __repr__(self): # or should it be __str__?
        return str(self.value) # str(), print(), repr() --> self.value

    def get_levels_num(self):
        # af and tech are dict b/c of non-regular increments
        if type(self.levels) is dict:
            return self.levels.get(self.value, 0)
        else: # returns avg value of that level out of 100
            step = 100/len(self.levels)
            i = step/2
            for level in self.levels:
                if level == self.value:
                    return int(i)
                else:
                    i += step
            return 0 ## for None / Depleted (reb,mp)

    def get_valint(self, parent_nation, key):
        if self.levels:
            valint = self.get_levels_num()
            # add entry into ints dict
            parent_nation.ints[key+'_int'] = valint
            return valint
        try:
            return int(self.value)
        except:
            pass

class Nation():
    def __init__(self, link):
        self.link = link
        self.stats = collections.OrderedDict()
        self.stats['id'] = Stat(keyword='id')
        self.stats['name'] = Stat(keyword='@Name:')
        self.stats['leader'] = Stat(keyword='@Leader:', offset=2)
        self.stats['afk'] = Stat(keyword='@AFK:')
        self.stats['approval'] = Stat(keyword='Approval:',
                                        levels=('Enemy of the People',
                                                'Utterly Despised',
                                                'Hated',
                                                'Disliked',
                                                'Middling',
                                                'Decent',
                                                'Liked',
                                                'Loved',
                                                'Adored',
                                                'Worshiped as a God'))
        self.stats['polsys'] = Stat(keyword='Political System:')
        self.stats['stab'] = Stat(keyword='Stability:',
                                    levels=('Brink of Collapse',
                                            'Mass Protests',
                                            'Rioting',
                                            'Chaotic',
                                            'Growing Tensions',
                                            'Seemingly Calm',
                                            'Quiet',
                                            'Very Stable',
                                            'Entrenched',
                                            'Unsinkable'))
        self.stats['land'] = Stat(keyword='Territory:')
        self.stats['rebels'] = Stat(keyword='Rebel Threat:',
                                    levels=('Scattered Terrorists',
                                            'Guerrillas',
                                            'Open Rebellion',
                                            'Civil War'))
        self.stats['pop'] = Stat(keyword='Population:')
        self.stats['qol'] = Stat(keyword='Quality of Life:',
                                    levels=('Humanitarian Crisis',
                                            'Disastrous',
                                            'Desperate',
                                            'Impoverished',
                                            'Poor',
                                            'Average',
                                            'Above Average',
                                            'Decent',
                                            'Good',
                                            'Developed'))
        self.stats['health'] = Stat(keyword='Healthcare:',
                                    levels=('Extinction Event',
                                            'Bodies in the Streets',
                                            'Diseased',
                                            'Desperation',
                                            'Very Poor',
                                            'Adequate',
                                            'Above Par',
                                            'Decent',
                                            'Above Average',
                                            'Great'))
        self.stats['lit'] = Stat(keyword='Literacy:')
        self.stats['unis'] = Stat(keyword='Universities:')
        self.stats['econsys'] = Stat(keyword='Economic System:')
        self.stats['faccos'] = Stat(keyword='Industry:')
        self.stats['gdp'] = Stat(keyword='Gross Domestic Product:')
        self.stats['growth'] = Stat(keyword='Growth:')
        self.stats['fi'] = Stat(keyword='Foreign Investment:',
                                value='0') # in case no FI
        self.stats['oilres'] = Stat(keyword='Discovered Oil Reserves:')
        self.stats['wells'] = Stat(keyword='Oil Production:')
        self.stats['mines'] = Stat(keyword='Raw Material Production:')
        self.stats['alignment'] = Stat(keyword='Official Alignment:')
        self.stats['region'] = Stat(keyword='Region:')
        self.stats['a_id'] = Stat(keyword='Alliance:')
        self.stats['a_name'] = Stat(keyword='Alliance:', offset=2)
        self.stats['rep'] = Stat(keyword='Reputation:',
                                    levels=('Axis of Evil',
                                            'Mad Dog',
                                            'Pariah',
                                            'Isolated',
                                            'Questionable',
                                            'Normal',
                                            'Good',
                                            'Nice',
                                            'Angelic',
                                            'Gandhi-Like'))
        self.stats['army'] = Stat(keyword='Army Size:')
        self.stats['manpower'] = Stat(keyword='Manpower:',
                                        levels=('Near Depletion',
                                                'Low',
                                                'Halved',
                                                'Plentiful',
                                                'Untapped'))
        self.stats['tech'] = Stat(keyword='Equipment:',
                                    levels={'Finest of the 19th century': 5,
                                            'First World War surplus': 30,
                                            'Second World War surplus': 100,
                                            'Korean War surplus': 225,
                                            'Vietnam War surplus': 400,
                                            'Almost Modern': 750,
                                            'Persian Gulf War surplus': 1500,
                                            'Advanced': 3000})
        self.stats['training'] = Stat(keyword='Training:',
                                        levels=('Undisciplined Rabble',
                                                'Poor',
                                                'Standard',
                                                'Good',
                                                'Elite'))
        self.stats['airforce'] = Stat(keyword='Airforce:',
                                        levels={'Meagre': 3,
                                                'Small': 6,
                                                'Mediocre': 9,
                                                'Somewhat Large': 12,
                                                'Large': 15,
                                                'Powerful': 18,
                                                'Very Powerful': 20})
        self.stats['navy'] = Stat(keyword='Navy:', offset=2)
        self.stats['atk_id'] = Stat(keyword='this nation!', offset=-1)
        self.stats['def_id'] = Stat(keyword='This nation', offset=-1)
        self.ints = collections.OrderedDict()

    # fill stats.value and stats.valint from dataList, using keyword and offset
    def fill_stats(self, dataList):
        for key, stat in self.stats.items():
            # traverse dataList backwards to avoid nation description
            for i in reversed(range(len(dataList)-1)):
                if dataList[i] == stat.keyword or key == 'id':
                    stat.value = self.get_value(key, stat, dataList, i)
            stat.valint = stat.get_valint(self, key)
        # merge stats and ints into one big dict
        self.stats.update(self.ints)
        # for key, stat in self.stats.items():
            # print('{}===={}'.format(key,stat))


    def get_value(self, key, stat, dataList, i):
        keyword = stat.keyword
        offset = stat.offset
        value = dataList[i+offset]
        levels = stat.levels
        # get id
        if key == 'id':
            value = self.link

        # tries to find alliance link (fails to None if no alliance)
        if key == 'a_id':
            try:
                search('alliancestats\.php\?allianceid=\d+', value).group(0)
            # no alliance link found --> return None
            except:
                return None
        # if a_name's value is this, that means there's no alliance link
        # so, there's no alliance, so return None
        elif key == 'a_name' and value == 'Alliance Votes Recieved:': # yes Recieved lmao rumcode
            return None

        # leave name, leader, and a_name alone (no whitespace strip)
        if key == 'name' or key == 'leader' or key == 'a_name':
            return value
        else: # all other values will be rstrip
            value = value.rstrip()
            # return value as text levels
            if levels: # app, stab, reb, qol, hc, rep, mp, tech, train, af
                return value
            else:
                try: # (id), afk, land, pop, lit, uni, econ shit, army, navy
                    # delete comma; allows negative nums
                    return search('-?\d+', value.replace(',','')).group(0)
                except:
                    if value == 'None' or value == 'online now':
                        return '0' # None/online now --> '0'
                    else: # polsys, econsys, alignment, region
                        return value

    # if stat.valint != value, add a new int entry into stats for csv purposes
    def push_valint(self):
        for key, stat in self.stats.items():
            if stat.valint is not None:
                try:
                    i = int(stat.value)
                except:
                    pass
                if i is not stat.valint:
                    self.ints[key+'_int'] = stat.valint
        self.stats.update(self.ints)

class World():
    def __init__(self):
        self.nations = []
        self.raw_values = []
        self.timestamp = now().strftime("%Y-%m-%d %H%Mh")
        print('world created at {}'.format(self.timestamp))

    def write_nations(self):
        header = list(self.nations[0].stats.keys()) # list of all keys in stats
        # print(header)
        with open(self.timestamp + '.csv', 'w') as f:
            print('writing to csv...')
            writer = csv.DictWriter(f, header, restval='MISSING VALUE', extrasaction='ignore')
            writer.writeheader()
            for nation in self.nations:
                writer.writerow(nation.stats)

    def update_sheet(self):
        with open(self.timestamp + '.csv', newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                self.raw_values.append(row)
        gc = pygsheets.authorize(service_file='service_creds.json')
        sh = gc.open_by_key('1tyG9AE817ZsLU2DHU64cAUGtqzuUcUcZhVCaG9LH4k0')
        ws1 = sh.worksheet_by_title("csv")
        ws1.clear()
        ws1.update_cells(crange='A1', values=self.raw_values)
        ws2 = sh.worksheet_by_title("overview")
        ws2.update_cell('B1', self.timestamp)

###################
#### FUNCTIONS ####
###################

def now():
    #server time = CST/CDT = -6/-5
    return datetime.utcnow() + timedelta(hours=-5)

"""
def reqURL(urlStr):
    req = Request(urlStr, data=None, headers={'User-Agent': 'Mozilla/5.0'})
    return urlopen(req).read()
#"""

async def get_html(s, url):
    async with s.get(url) as resp:
        print('GETting... {}'.format(url))
        assert resp.status == 200
        html = await resp.text()
    try: # get rid of bottom banner ad
        pattern = r'<div style="border: solid white 1px; height: 100px; width: 500px; overflow: hidden;">.*?<\/div>'
        html = sub(pattern, '', html)
    except:
        pass
    return html

###############
#### START ####
###############

async def main(session):
    print('Running... Maintain internet connection.')
    global current_world
    current_world = World()
    nation_links = await get_nation_links(session)
    parse_nations = [parse_nation(session, link) for link in nation_links]
    current_world.nations = await asyncio.gather(*parse_nations)
    # htmls = [get_html(session, link) for link in nation_links]
    # HTMLS = await asyncio.gather(*htmls)
    # for i in range(len(HTMLS)):
    #     parser = dataParser(strict=False)
    #     parser.feed(HTMLS[i])
    #     current_nation = Nation(nation_links[i])
    #     current_nation.fill_stats(parser.dataList)
    #     current_nation.push_valint()
    #     current_world.nations.append(current_nation)
    current_world.write_nations()
    current_world.update_sheet()

async def parse_nation(session, url):
    nation_html = await get_html(session, url)
    parser = dataParser(strict=False)
    parser.feed(nation_html)
    current_nation = Nation(url)
    current_nation.fill_stats(parser.dataList)
    # current_nation.push_valint()
    return current_nation

async def get_nation_links(session):
    nation_links = []
    last_page = await get_last_page(session, nation_links)
    # last_page = 2
    rs = [get_ranking(session, i, nation_links) for i in range(2,last_page+1)]
    await asyncio.gather(*rs)
    return nation_links

async def get_last_page(session, nation_links):
    r1 = await get_ranking(session, 1, nation_links)
    pagination = search(r'<ul class="pagination">.+?<\/ul>', r1).group(0)
    last_page = findall(r'(?<=rankings\.php\?page=)\d+', pagination)[-1]
    return int(last_page)

async def get_ranking(session, i, nation_links):
    rank_url = 'http://blocgame.com/rankings.php?page='
    r = await get_html(session, '{}{}'.format(rank_url, i))
    links = findall(r'(?<=<a href=")stats\.php\?id=\d+(?=">)',r)
    for l in links:
        nation_links.append('http://blocgame.com/'+l)
    return r

async def wrapper(loop):
    begin = now()
    print(begin)
    async with aiohttp.ClientSession(loop=loop) as session:
        await main(session)
    end = now()
    print(end)
    print(end - begin)

loop = asyncio.get_event_loop()
loop.run_until_complete(wrapper(loop))

##########################
#### DEBUGGING NATION ####
##########################

# from BLOC_html import html
# parser = dataParser(strict=False)
# parser.feed(html)
# current_nation = Nation('http://blocgame.com/stats.php?id=420')
# current_nation.fill_stats(parser.dataList)
# current_nation.push_valint()
# for key, stat in current_nation.stats.items():
#     print('{}----{}'.format(key, stat))
# current_world = World()
# current_world.nations = [current_nation]
# current_world.write_nations()
