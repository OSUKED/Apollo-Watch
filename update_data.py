"""
Imports
"""
import os
import re
import json
import requests
import pandas as pd
import FEAutils as hlp
from warnings import warn
from dotenv import load_dotenv

"""
Price Data Functions
"""
def retrieve_market_prices():
    prices_url = 'https://www.apolloenergy.co.uk/news/current-uk-energy-prices'
    markets = ['Power', 'Gas', 'Brent & Coal']
    
    r = requests.get(prices_url)
    tables = pd.read_html(r.text)

    price_data = [df.set_index(df.columns[0]).T.to_dict() for df in tables]
    price_data = dict(zip(markets, price_data))
    
    return price_data


"""
Market Analysis Functions
"""
create_analysis_url = lambda date: f"https://www.apolloenergy.co.uk/news/energy-market-analysis-{pd.to_datetime(date).strftime('%d-%m-%Y')}"

def get_analysis_date():
    current_weekday = pd.Timestamp.now().weekday()

    if current_weekday > 4:
        days_to_offset = current_weekday - 4
        date = (pd.Timestamp.now() - pd.Timedelta(days=days_to_offset)).strftime('%Y-%m-%d')

    return date

def handle_error_message(message, webhook_url=None):
    warn(message)

    if webhook_url is not None:
        hlp.send_slack_msg(message, webhook_url)    
    
    json_message = {'message': message}
    
    return json_message

def extract_market_analysis(analysis_url):
    r = requests.get(analysis_url)
    tables = pd.read_html(r.text)
    
    power_data = tables[0].iloc[:, 0].to_list()
    gas_data = tables[0].iloc[:, 1].to_list()

    brent_analysis_txt = tables[1].iloc[0, 0]
    brent_sections = ['Brent Summary', '1-year forward prices']
    brent_content = [elem.strip() for elem in re.split(' |'.join(brent_sections), brent_analysis_txt) if elem != '']
    brent_data = dict(zip(brent_sections, brent_content))

    market_analysis = {
        power_data[0]: {
            power_data[1]: power_data[2],
            power_data[3]: power_data[4]
        },
        gas_data[0]: {
            gas_data[1]: gas_data[2],
            gas_data[3]: gas_data[4]
        },
        'Brent': brent_data
    }
    
    return market_analysis 

def clean_market_analysis(market_analysis):
    char_replacements = {
        'â\x80\x98': '\'',
        'â\x80\x99': '\'',
        'Â': '',
        "Today's prices can also be found in an easy to read table on our 'current UK energy price' page.": ''
    }

    for mkt, analysis in market_analysis.items():
        for analysis_section, section_content in analysis.items():
            for old, new in char_replacements.items():
                section_content = section_content.replace(old, new)

            market_analysis[mkt][analysis_section] = section_content

    return market_analysis

def retrieve_cleaned_market_analysis(webhook_url=None):
    date = get_analysis_date()
    analysis_url = create_analysis_url(date)
    
    try:
        requests.get(analysis_url).raise_for_status() # checks page can be retrieved
    except:
        message = f'A market analysis page could not be found for {date}'
        json_message = handle_error_message(message, webhook_url)
            
        return json_message
        
    market_analysis = extract_market_analysis(analysis_url)
    market_analysis = clean_market_analysis(market_analysis)
    
    return market_analysis


"""
General Helper Functions
"""
def update_readme_time(readme_fp, 
                       splitter='Last updated: ', 
                       dt_format='%Y-%m-%d %H:%M'):
    
    with open(readme_fp, 'r') as readme:
        txt = readme.read()
    
    start, end = txt.split(splitter)
    old_date = end[:16]
    end = end.split(old_date)[1]
    new_date = pd.Timestamp.now().strftime(dt_format)
    
    new_txt = start + splitter + new_date + end
    
    with open(readme_fp, 'w') as readme:
        readme.write(new_txt)
        
    return


"""
Loading Environment Variables
"""
load_dotenv('.env')
webhook_url = os.getenv('SLACK_WEBHOOK_URL')


"""
Retrieval Process
"""
retrieval_steps = {
     'market_analysis': {
         'func': retrieve_cleaned_market_analysis,
         'error_message': f'The market analysis page for {get_analysis_date()} could not be retrieved/processed'
     },
     'market_prices': {
         'func': retrieve_market_prices,
         'error_message': 'The latest market prices could not be retrieved'
     },
 }

for retrieval_step, (func, error_message) in retrieval_steps.items():
    try:
        data = func(webhook_url)
    except:
        data = handle_error_message(error_message, webhook_url)

    with open(f'data/{retrieval_step}.json', 'w') as fp:
        json.dump(data, fp)
    
update_readme_time('README.md')