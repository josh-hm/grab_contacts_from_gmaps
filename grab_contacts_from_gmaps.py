'''This contains a script to generate a CSV file containing the
contact information for all establishments from Google Places for
given postal code(s) (default country, United States).

Please see the README for more information.
'''

from collections import namedtuple
from getpass import getpass
import os
import pickle
import re
import sys
import time

import argparse
from bs4 import BeautifulSoup
from geopy.distance import great_circle
import pandas as pd
import pycountry
import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib.parse import urlparse


# ERRORS
class ApiStatusError(Exception):
    pass

class UnacceptedInput(Exception):
    pass


# NAMED TUPLES
Coordinates = namedtuple('Coordinates', 'lat, lng, rad')

DataRow = namedtuple('DataRow', 'establishment, phone_number, address, '
                     'locality, city, state, postal_code, website, data_source')

AddressComponents = namedtuple('AddressComponents',
                               'address, locality, city, state, postal_code')


# METHODS
def set_key(key, file_name='./.ga_key'):

    '''Create a hidden file of google api key from a string
    '''

    with open(file_name, 'bw+') as pw:
        pickle.dump(key, pw)


def get_key(file_name='./.ga_key'):

    '''Returns the google api key needed for all requests
    '''

    try:
        with open(file_name, 'br') as pr:
            key = pickle.load(pr)

    except FileNotFoundError:
        answer = input('Google API key not found. Do you want to enter it now? '
                       '[(y)es/(n)o) :').lower()
        if answer.starts_with('y'):
            key = getpass(prompt='Type / Paste API key and then press enter/return: ')
            set_key(key)
            print('Saved to filepath default, "./.ga_key"')

        else:
            print('Cannot run without a Google API key. '
                  'Please try again when you have one.')
            pass

    return key


def check_establishment(establishment):

    '''Checks if the inputted establishment is on the Google Places API list
    '''
    
    accepted_types = ['accounting', 'airport', 'amusement_park', 'aquarium',
                      'art_gallery', 'atm', 'bakery', 'bank', 'bar',
                      'beauty_salon', 'bicycle_store', 'book_store',
                      'bowling_alley', 'bus_station', 'cafe', 'campground',
                      'car_dealer', 'car_rental', 'car_repair', 'car_wash',
                      'casino', 'cemetery', 'church', 'city_hall',
                      'clothing_store', 'convenience_store', 'courthouse',
                      'dentist', 'department_store', 'doctor', 'electrician',
                      'electronics_store', 'embassy', 'fire_station',
                      'florist', 'funeral_home', 'furniture_store',
                      'gas_station', 'gym', 'hair_care', 'hardware_store',
                      'hindu_temple', 'home_goods_store', 'hospital',
                      'insurance_agency', 'jewelry_store', 'laundry',
                      'lawyer', 'library', 'light_rail_station',
                      'liquor_store', 'local_government_office',
                      'locksmith', 'lodging', 'meal_delivery',
                      'meal_takeaway', 'mosque', 'movie_rental',
                      'movie_theater', 'moving_company', 'museum',
                      'night_club', 'painter', 'park', 'parking', 'pet_store',
                      'pharmacy', 'physiotherapist', 'plumber', 'police',
                      'post_office', 'real_estate_agency', 'restaurant',
                      'roofing_contractor', 'rv_park', 'school', 'shoe_store',
                      'shopping_mall', 'spa', 'stadium', 'storage', 'store',
                      'subway_station', 'synagogue', 'taxi_stand',
                      'train_station', 'transit_station', 'travel_agency',
                      'university', 'veterinary_care', 'zoo']

    if establishment not in accepted_types:
        print('Invalid establishmet type. Please use a type from '
              'the following list\n')
        print('{}\n'.format(accepted_types))

        raise UnacceptedInput

    return


def check_state_code(state_code):
 
    '''Checks if the inputted state_code is in the provided state--csv zipcode
    '''
 
    accepted_state_codes = ['AA', 'AK', 'AL', 'AP', 'AR', 'AZ', 'CA', 'CO', 'CT',
                            'DC', 'DE', 'FL', 'FM', 'GA', 'HI', 'IA', 'ID', 'IL',
                            'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MH', 'MI',
                            'MN', 'MO', 'MP', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH',
                            'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'PW',
                            'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VA', 'VT', 'WA',
                            'WI', 'WV', 'WY']
 
    if state_code not in accepted_state_codes:
        print('Invalid state code. Please use a type from '
              'the following list\n')
        print('{}\n'.format(accepted_state_codes))
 
        raise UnacceptedInput
 
    return


def get_string(soup_data):

    '''Returns the plain-string for the given soup_data if it exists
    '''

    try:
        return soup_data.string
    except AttributeError:
        return ''


def check_status(soup, url):

    '''Throws an exception if Google API status code is non-normal
    '''

    if get_string(soup.status) not in ('OK', 'ZERO_RESULTS'):
        print(get_string(soup.status))
        print(url)
        raise ApiStatusError


def make_soup(base_query, payload='', rtrn_url=False):

    '''Returns a parsable BeautifulSoup object from a HTTP request query
    '''
    try:
        page = requests.get(base_query, params=payload, timeout=10)
    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError):
        raise
    soup = BeautifulSoup(page.text, 'lxml')
    check_status(soup, page.url)

    return (soup, page.url) if rtrn_url else soup


def get_radius(geo_data):

    '''Returns a distance (m) that will span the geo-data given
    '''

    ne_coor = (float(geo_data.viewport.northeast.lat.string),
               float(geo_data.viewport.northeast.lng.string))
    sw_coor = (float(geo_data.viewport.southwest.lat.string),
               float(geo_data.viewport.southwest.lng.string))

    ne_to_sw = great_circle(ne_coor, sw_coor).meters
    radius = ne_to_sw * .6

    return radius


def get_coordinates(postal_code, country_code='US'):

    '''Returns a Coordinates namedtuple for the postal code and radius given
    '''

    base_query = 'https://maps.googleapis.com/maps/api/geocode/xml'
    payload = {'components': 'postal_code:{}|country:{}'.format(postal_code, country_code),
               'key': get_key()}
    soup, url = make_soup(base_query, payload, rtrn_url=True)

    geo_data = soup.geometry
    if geo_data:
        radius = get_radius(geo_data)
        coors = Coordinates(lat=soup.geometry.location.lat.string,
                            lng=soup.geometry.location.lng.string,
                            rad=radius)
    else:
        print('POSTAL CODE {} NOT FOUND IN GOOGLE GEOCODING API'.format(postal_code))
        print(url)
        coors = None

    return coors


def get_place_ids(establishment, latitude, longitude, radius):

    '''Return a list of google place_ids for the given coordinates
    '''

    base_query = 'https://maps.googleapis.com/maps/api/place/nearbysearch/xml'
    payload = {'location': '{},{}'.format(latitude, longitude),
               'radius': radius,
               'type': establishment,
               'key': get_key(),
               'pagetoken': ''}

    place_ids = list()
    next_page = True

    while next_page:
        soup = make_soup(base_query, payload)
        place_ids.extend([tag.string for tag in soup.find_all('place_id')])
        try:
            payload['pagetoken'] = soup.next_page_token.string
        except AttributeError:
            next_page = False
        if next_page:
            time.sleep(2)  # to ensure script doesn't break usage rate limits

    return place_ids


def remove_duplicates(place_ids):

    '''Returns a deduplicated list of place_ids

    This function is necessary as the areas of search
    created by get_coordinates() may overlap.
    '''

    return list(set(place_ids))


def get_address_components(address_components):

    '''Returns a AddressComponents namedtuple from the given components.
    '''

    address, city, state, postal_code = '', '', '', ''

    for comp in address_components:
        if get_string(comp.type) == 'street_number':
            address = comp.long_name.string
        elif get_string(comp.type) == 'route':
            address = ' '.join((address, comp.long_name.string))
        elif get_string(comp.type) == 'locality':
            locality = comp.long_name.string
        elif get_string(comp.type) == 'administrative_area_level_2':
            city = comp.long_name.string
        elif get_string(comp.type) == 'administrative_area_level_1':
            state = comp.long_name.string
        elif get_string(comp.type) == 'postal_code':
            postal_code = comp.long_name.string
        elif get_string(comp.type) == 'postal_code_suffix':
            postal_code = '-'.join((postal_code, comp.long_name.string))

    return AddressComponents(address, locality, city, state, postal_code)


def get_establishment_data(place_id):

    '''Return a row of data for the given google place_id
    '''

    base_query = 'https://maps.googleapis.com/maps/api/place/details/xml?'
    fields = ['name', 'address_component', 'formatted_phone_number', 'website']
    payload = {'placeid': place_id,
               'fields': ','.join(fields),
               'key': get_key()}
    soup, data_source = make_soup(base_query, payload, rtrn_url=True)

    establishment = get_string(soup.find_all('name')[0])
    raw_number = get_string(soup.formatted_phone_number)
    phone_number = re.sub(r'\D', '', raw_number) if raw_number else ''
    addr = get_address_components(soup.find_all('address_component'))
    website = get_string(soup.website)

    data_row = DataRow(establishment, phone_number, addr.address, addr.locality,
                       addr.city, addr.state, addr.postal_code, website, data_source)

    return data_row


def write_to_log(establishment, postal_code, country_code):

    '''Writes postal code to logfile when no establishments are found in postal code
    '''

    logfolder = os.path.join('data', establishment, country_code, 'logs')
    if not os.path.isdir(logfolder):
        os.makedirs(logfolder)
    logfile = os.path.join(logfolder, 'logfile')
    with open(logfile, 'a+') as wa:
        wa.write('{}\n'.format(postal_code))

    return


def write_establishment_data(data, establishment, postal_code, country_code):

    '''Write concatenated data to CSV file
    '''

    header = DataRow._fields
    df = pd.DataFrame(data, columns=header)

    df = df[df.postal_code.str.startswith(postal_code)]
    if not df.empty:
        data_folder = os.path.join('data', establishment, country_code)
        if not os.path.isdir(data_folder):
            os.makedirs(data_folder)
        csv_file = os.path.join(data_folder, '{}.csv'.format(postal_code))
        df.to_csv(csv_file, index=False, encoding='utf-8')
        return True
    else:
        write_to_log(establishment, postal_code, country_code)
        return False


def check_current_data(establishment, country_code, postal_list, state_code):

    '''Returns a list of postal codes to-be-grabbed after checking current data
    '''

    postal_code_num_all = len(postal_list)
    data_folder = os.path.join('data', establishment, country_code)
    if not os.path.isdir(data_folder):
        os.makedirs(data_folder)

    # Remove already created postal codes from postal_list
    created_postal_list = list()
    for dirs, folders, files in os.walk(data_folder):
        files = [f for f in files if re.match(r'\d\d\d\d\d.csv', f)]
        created_postal_list.extend([int(f[:-4]) for f in files
                                   if int(f[:-4]) in postal_list])
    for postal_code in created_postal_list:
        postal_list.remove(postal_code)
    postal_code_num_wo_created = len(postal_list)
    postal_code_num_diff_1 = postal_code_num_all - postal_code_num_wo_created
    print('{} postal code CSVs already created for {}'.format(postal_code_num_diff_1,
                                                              state_code))

    # Remove already tried postal codes from postal_list
    logfolder = os.path.join('data', establishment, country_code, 'logs')
    logfile = os.path.join(logfolder, 'logfile')
    if not os.path.isdir(logfolder):
        os.makedirs(logfolder)
        open(logfile, 'a+').close()
    with open(logfile, 'r') as r:
        tried_postal_list = [int(l.rstrip('\n')) for l in r.readlines()]
    for postal_code in tried_postal_list:
        postal_list.remove(postal_code)
    postal_code_num_wo_tried = len(postal_list)
    postal_code_num_diff_2 = postal_code_num_wo_created - postal_code_num_wo_tried
    print('{} previously searched postal codes have no '
          '{} in {}'.format(postal_code_num_diff_2, establishment, state_code))

    return (postal_list, postal_code_num_diff_1 + postal_code_num_diff_2)


def concatenate_postal_codes_for_state(establishment, country_code, postal_list, state_code):

    '''Merges every postal code CSV for a given place-type and state
    '''

    df = pd.DataFrame(columns=['establishment', 'phone_number', 'address', 'city',
                               'state', 'postal_code', 'website', 'data_source'])
    folder_path = os.path.join('data', establishment, country_code)
    for root, dirs, files in os.walk(folder_path):
        files = [f for f in files if f[0] != '.']
        for filename in files:
            if filename[:-4] in postal_list:
                f_path = os.path.join(folder_path, filename)
                temp_df = pd.read_csv(f_path)
                df = pd.concat((df, temp_df))

    df = df.drop_duplicates()
    out_file = os.path.join(folder_path, '{}_all_postal_codes.csv'.format(state_code))
    df.to_csv(out_file, index=False)
    print('Full {} CSV for {} created'.format(establishment, state_code))
    
    return


def find_email_addresses(soup, url):

    '''Helper for get_emails(), returns email addresses found on a given website and it's contact page
    '''
    email_regex = re.compile(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)')

    link_list = [a.get('href') for a in soup.find_all('a') if a.get('href') is not None]
    link_list.extend([a.get_text() for a in soup.find_all('a')])
    potential_emails = email_regex.findall(' '.join(link_list))

    contact_paths = [link for link in link_list if (('contact' in link.lower()))]
    parsed_url = urlparse(url)
    clean_url = '{p.scheme}://{p.netloc}{p.path}'.format(p=parsed_url)
    contact_pages = [''.join((clean_url, c_path)) for c_path in contact_paths]
    contact_pages = list(set(contact_pages))

    for page in contact_pages:
        ret_page = requests.get(page, timeout=10)
        soup_2 = BeautifulSoup(ret_page.text, 'lxml')
        link_list_2 = [a.get('href') for a in soup_2.find_all('a')
                       if a.get('href') is not None]
        link_list_2.extend([a.get_text() for a in soup_2.find_all('a')])
        potential_emails_2 = email_regex.findall(' '.join(link_list_2))
        potential_emails.extend(potential_emails_2)

    set_emails = list(set(potential_emails))
            
    return set_emails


def get_emails(url):

    '''Returns email addresses found on a given website and it's contact page
    '''

    if pd.isnull(url):
        return ''

    try:
        page = requests.get(url, timeout=10)
        soup = BeautifulSoup(page.text, 'lxml')
        emails = find_email_addresses(soup, url)
    except Exception as e:
        # TODO :: add better error handling
        print(e)
        emails = list()

    return emails


def append_emails_to_copy_of_csv(csv_path, url_column_name='website', overwrite=True):

    '''Creates a copy of the CSV path given "*_with_emails.csv" that includes emails
    '''

    ext_index = csv_path.find('.csv')
    new_path = csv_path[:ext_index] + '_with_emails.csv'

    if not overwrite:
        if os.path.isfile(new_path):
            print('\n{} already exists'.format(new_path))
            return
    
    print('Generating CSV with emails from {}'.format(csv_path))
    tqdm.pandas()
    df = pd.read_csv(csv_path)
    df['emails'] = df[url_column_name].progress_apply(get_emails)
    df_emails = pd.DataFrame(df.emails.values.tolist(),
                             index=df.index).add_prefix('email_')
    df = pd.concat((df, df_emails), axis=1)
    df.to_csv(new_path, index=False)
    print('CSV with emails created from {}'.format(csv_path))
    return


def grab_data_for_postal_code(establishment, postal_code, country_code):

    '''Create a CSV file containing contact data for a given place-type and postal code
    '''

    check_establishment(establishment)

    postal_code = '{:05}'.format(int(postal_code))
    coors = get_coordinates(postal_code, country_code)
    if coors:
        place_ids = get_place_ids(establishment,
                                  coors.lat, coors.lng,
                                  coors.rad)
        establishment_data = [get_establishment_data(pid) for pid in place_ids]
        created = write_establishment_data(establishment_data, establishment,
                                           postal_code, country_code)
        if created:
            print('{} CSV for postal code {} created  '.format(establishment, postal_code),
                  end='')
        else:
            print('no {} found for postal code {}     '.format(establishment, postal_code),
                  end='')
    else:
        print('no {} found for postal code {}     '.format(establishment, postal_code),
              end='')

    return


def grab_data_for_state(establishment, state_code, country_code):

    '''Create a CSV file containing contact data for a given place-type and state
    '''

    check_establishment(establishment)
    check_state_code(state_code)

    state_postal_code_file = './us_postal_codes.csv'
    df = pd.read_csv(state_postal_code_file, engine='python')
    postal_list = list(set(df[df['State Abbreviation'] == state_code]['Zip Code']))
    postal_code_num_all = len(postal_list)
    postal_list, postal_code_num_diff = check_current_data(establishment, country_code, 
                                                           postal_list, state_code)

    for e, postal_code in enumerate(postal_list):
        grab_data_for_postal_code(establishment, postal_code, country_code)
        print('|{:04}/{:04}|'.format(e + postal_code_num_diff + 1, postal_code_num_all))

    concatenate_postal_codes_for_state(establishment, country_code, postal_list, state_code)
    return


# MAIN
if __name__ == '__main__':
    desc =  ('This script will make a CSV file of the contact data, including '
             'email addresses, for the establishments of the given type that are '
             'located in the given postal code.\n\n'
             'Data for postcode searches will be written to file:\n'
             './data/[establishment]/[country_code]/[postal_code].csv\n\n'
             'The default setting is to search one US postal code.  If you\'d like '
             'to exercise different options, such as collecting data for multiple '
             'establishment types or postal codes, choosing a different country, or to '
             'omit collecting email addresses, please run the command with the help '
             'flag, "python3 grab_contacts_from_gmaps.py -h" to see how you can do that.')
            
    parser = argparse.ArgumentParser(description=desc,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    accepted_establishments = ['accounting', 'airport', 'amusement_park', 'aquarium',
                               'art_gallery', 'atm', 'bakery', 'bank', 'bar',
                               'beauty_salon', 'bicycle_store', 'book_store',
                               'bowling_alley', 'bus_station', 'cafe', 'campground',
                               'car_dealer', 'car_rental', 'car_repair', 'car_wash',
                               'casino', 'cemetery', 'church', 'city_hall',
                               'clothing_store', 'convenience_store', 'courthouse',
                               'dentist', 'department_store', 'doctor', 'electrician',
                               'electronics_store', 'embassy', 'fire_station',
                               'florist', 'funeral_home', 'furniture_store',
                               'gas_station', 'gym', 'hair_care', 'hardware_store',
                               'hindu_temple', 'home_goods_store', 'hospital',
                               'insurance_agency', 'jewelry_store', 'laundry',
                               'lawyer', 'library', 'light_rail_station',
                               'liquor_store', 'local_government_office',
                               'locksmith', 'lodging', 'meal_delivery',
                               'meal_takeaway', 'mosque', 'movie_rental',
                               'movie_theater', 'moving_company', 'museum',
                               'night_club', 'painter', 'park', 'parking', 'pet_store',
                               'pharmacy', 'physiotherapist', 'plumber', 'police',
                               'post_office', 'real_estate_agency', 'restaurant',
                               'roofing_contractor', 'rv_park', 'school', 'shoe_store',
                               'shopping_mall', 'spa', 'stadium', 'storage', 'store',
                               'subway_station', 'synagogue', 'taxi_stand',
                               'train_station', 'transit_station', 'travel_agency',
                               'university', 'veterinary_care', 'zoo']

    accepted_state_codes = ['AA', 'AK', 'AL', 'AP', 'AR', 'AZ', 'CA', 'CO', 'CT',
                            'DC', 'DE', 'FL', 'FM', 'GA', 'HI', 'IA', 'ID', 'IL',
                            'IN', 'KS', 'KY', 'LA', 'MA', 'MD', 'ME', 'MH', 'MI',
                            'MN', 'MO', 'MP', 'MS', 'MT', 'NC', 'ND', 'NE', 'NH',
                            'NJ', 'NM', 'NV', 'NY', 'OH', 'OK', 'OR', 'PA', 'PW',
                            'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VA', 'VT', 'WA',
                            'WI', 'WV', 'WY']

    accepted_country_codes = [c.alpha_2 for c in pycountry.countries]

    parser.add_argument('-e', '--establishment', nargs='+', choices=accepted_establishments,
                        help=str('\nInput one or more of the establishment types listed above '
                                 'to determine from which organizations you collect contact '
                                 'info.  If you use this option you must also specify the '
                                 'postal code(s) with "-p"/"--postalcode".\n \n'))
    parser.add_argument('-p', '--postalcode', nargs='+', metavar='POSTAL CODE',
                        help=str('\nInput one or more postal codes to determine from which '
                                 'postal codes you collect contact info.  If you use this '
                                 'option you must also specify the establishment type(s) with '
                                 'with "-e"/"--establishment".\n \n'))
    parser.add_argument('-s', '--statecode', nargs='?', choices=accepted_state_codes, 
                        help=str('\nOnly used in conjunction with the "--fullstate" flag, and '
                                 'can only used for the US.  Input one of the state codes to '
                                 'grab contact info for the chosen establishment(s).\n \n'))
    parser.add_argument('-c', '--countrycode', nargs='?', default='US',
                        choices=accepted_country_codes,
                        help=str('\nIf you want to search non-US postal codes, input one '
                                 'of the 2-letter country codes listed above.  If you '
                                 'use this option you must also specify the establishment '
                                 'type(s) with "-e"/"--establishment" and postal code(s) '
                                 'with "-p"/"--postal".\n \n'))
    parser.add_argument('-a', '--appendOnly', nargs='?', metavar='CSV PATH',
                        help=str('\nIf you want to add emails to an existing contact file, '
                                 'run this option with the path to the CSV file you want to '
                                 'add emails to.\n \n'))
    parser.add_argument('-o', '--omitEmails', action='store_true',
                        help=str('\nUse this flag if you\'d like to skip the email scraping '
                                 'step of the process.\n \n'))
    parser.add_argument('-f', '--fullState', action='store_true',
                        help=str('\nUse this flag if you\'d like to grab the contact info from '
                                 'an entire US state.  If you use this option, you must also '
                                 'specify the establishment type(s) with "-e"/"--establishment". '
                                 'step of the process.\n \n'))
    
    args = parser.parse_args()

    if args.fullstate:
        if not all((args.statecode, args.establishment)) and args.countrycode == 'US':
            print('If you use the fullstate flag, the countrycode must be "US", you '
                  'must also use the establishment and statecode option.\n'
                  'Use "python3 grab_contacts_from_gmaps.py -h" to get more info\n')
        else:
            for establishment in args.establishment:
                grab_data_for_state(establishment, args.statecode, args.countrycode)
                if not args.omitemails:
                    csv_path = os.path.join('data', establishment, args.countrycode, 
                                            '{}_all_postal_codes.csv'.format(args.statecode))
                    append_emails_to_copy_of_csv(csv_path)
    elif all((args.establishment, args.postalcode)):
        for establishment in args.establishment:
            for postal_code in args.postalcode:
                grab_data_for_postal_code(establishment, postal_code, args.countrycode)
                if not args.omitemails:
                    csv_path = os.path.join('data', establishment, args.countrycode,
                                            '{}.csv'.format(postal_code))
                    append_emails_to_copy_of_csv(csv_path)
    elif any((args.establishment, args.postalcode)):
        if args.countrycode == 'US':
            print('You must use the establishment and postal code options together.\n'
                  'Use "python3 grab_contacts_from_gmaps.py -h" to get more info\n')
        else:
            print('If you use the countrycode option, you must also use the '
                  'establishment and postal code option.\n'
                  'Use "python3 grab_contacts_from_gmaps.py -h" to get more info\n')
    else:
        print('\n\n' + desc + '\n\n')
        establishment = input('Establishment type?: ').lower()
        postal_code = input('Postal code: ')
        if not re.match(r'\d\d\d\d\d', postal_code):
             print('Invalid postal code. Five digit codes only\n')
             raise UnacceptedInput

        grab_data_for_postal_code(establishment, postal_code, country_code=args.countrycode)
        csv_file = os.path.join('data', establishment, args.countrycode, '{}.csv'.format(postal_code))
        append_emails_to_copy_of_csv(csv_file)
        print()
    sys.exit(0)
