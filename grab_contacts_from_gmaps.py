'''This contains a script to generate a CSV file containing the
contact information for all establishments from Google Places for a
given US state or zipcode.

Please see the README for more information.
'''

from collections import namedtuple
from getpass import getpass
import os
import pickle
import re
import sys
import time

from bs4 import BeautifulSoup
from geopy.distance import great_circle
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from tqdm import tqdm
from urllib.parse import urlparse



# ERRORS

class ApiStatusError(Exception):
    pass

class DataFileExistsError(Exception):
    pass

class LogFolderError(Exception):
    pass

class ContinueAnyway(Exception):
    pass

class UnacceptedInput(Exception):
    pass


# NAMED TUPLES

Coordinates = namedtuple('Coordinates', 'lat, lng, rad')

DataRow = namedtuple('DataRow', 'establishment, phone_number, address,'
                     'city, state, zipcode, website, data_source')

AddressComponents = namedtuple('AddressComponents',
                               'address, city, state, zipcode')


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


def accepted_state_code(state_code):

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

    return True


def accepted_establishment(establishment):

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

    return True


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


def get_coordinates(zipcode, err_count=0):

    '''Returns a Coordinates namedtuple for the zipcode and radius given
    '''

    base_query = 'https://maps.googleapis.com/maps/api/geocode/xml'
    payload = {'components': 'postal_code:{}'.format(zipcode),
               'key': get_key()}
    soup, url = make_soup(base_query, payload, rtrn_url=True)

    geo_data = soup.geometry
    if geo_data:
        radius = get_radius(geo_data)
        coors = Coordinates(lat=soup.geometry.location.lat.string,
                            lng=soup.geometry.location.lng.string,
                            rad=radius)
    else:
        print('ZIPCODE {} NOT FOUND IN GOOGLE GEOCODING API'.format(zipcode))
        print(url)
        coors = None

    return coors


def get_place_ids(establishment, latitude, longitude, radius, err_count=0):

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

    '''Returns a dedupped list of place_ids

    This function is necessary as the areas of search
    created by get_coordinates() may overlap.
    '''

    return list(set(place_ids))


def get_address_components(address_components):

    '''Returns a AddressComponents namedtuple from the given componments.
    '''

    address, city, state, zipcode = '', '', '', ''

    for comp in address_components:
        if get_string(comp.type) == 'street_number':
            address = comp.long_name.string
        elif get_string(comp.type) == 'route':
            address = ' '.join((address, comp.long_name.string))

        elif get_string(comp.type) == 'locality':
            city = comp.long_name.string

        elif get_string(comp.type) == 'administrative_area_level_1':
            state = comp.long_name.string

        elif get_string(comp.type) == 'postal_code':
            zipcode = comp.long_name.string
        elif get_string(comp.type) == 'postal_code_suffix':
            zipcode = '-'.join((zipcode, comp.long_name.string))

    return AddressComponents(address, city, state, zipcode)


def get_establishment_data(place_id, err_count=0):

    '''Return a row of data for the given google place_id
    '''

    base_query = 'https://maps.googleapis.com/maps/api/place/details/xml?'
    payload = {'placeid': place_id,
               'key': get_key()}
    soup, data_source = make_soup(base_query, payload, rtrn_url=True)

    establishment = get_string(soup.find_all('name')[0])
    raw_number = get_string(soup.formatted_phone_number)
    phone_number = re.sub(r'\D', '', raw_number) if raw_number else ''
    addr = get_address_components(soup.find_all('address_component'))
    website = get_string(soup.website)

    data_row = DataRow(establishment, phone_number, addr.address, addr.city,
                       addr.state, addr.zipcode, website, data_source)

    return data_row


def write_to_log(establishment, zipcode, state_code):

    '''Writes zipcode to logfile when no establishments are found in zipcode
    '''

    if not os.path.isdir(os.path.join('data', establishment, 'logs', state_code)):
            os.makedirs(os.path.join('data', establishment, 'logs', state_code))
    logfile = os.path.join('data', establishment, 'logs', state_code, 'logfile')
    with open(logfile, 'a+') as wa:
        wa.write('{}\n'.format(zipcode))

    return


def write_establishment_data(data, establishment, zipcode, state_code):

    '''Write concatenated data to csv file
    '''

    header = ['establishment', 'phone_number', 'address',
              'city', 'state', 'zipcode', 'website', 'data_source']

    df = pd.DataFrame(data, columns=header)

    df = df[df.zipcode.str.startswith(zipcode)]
    if not df.empty:
        if not os.path.isdir(os.path.join('data', establishment, state_code)):
            os.makedirs(os.path.join('data', establishment, state_code))
        csv_file = os.path.join('data', establishment, state_code, zipcode) + '.csv'
        df.to_csv(csv_file, index=False, encoding='utf-8')
        return True
    else:
        write_to_log(establishment, zipcode, state_code)
        return False


def check_current_data(zip_list, establishment, state_code):

    '''Returns a list of zipcodes to-be-grabbed after checking current data
    '''

    zip_num_all = len(zip_list)
    data_folder = os.path.join('data', establishment, state_code)
    if not os.path.isdir(data_folder):
        os.makedirs(data_folder)

    # Remove already created zipcodes from zip_list
    created_zip_list = list()
    for dirs, folders, files in os.walk(data_folder):
        for filename in files:
            try:
                created_zip_list.append(int(filename[:-4]))
            except ValueError:
                if filename[:-4].endswith('all_zipcodes'):
                    raise DataFileExistsError
                else:
                    raise LogFolderError
    for z in created_zip_list:
        zip_list.remove(z)
    zip_num_wo_created = len(zip_list)
    zip_num_diff_1 = zip_num_all - zip_num_wo_created
    print('{} zipcode csvs already created for {}'.format(zip_num_diff_1,
                                                          state_code))

    # Remove already tried zipcodes from zip_list
    logfolder = os.path.join('data', establishment, 'logs', state_code)
    logfile = os.path.join(logfolder, 'logfile')
    if not os.path.isdir(logfolder):
        os.makedirs(logfolder)
        open(logfile, 'a+').close()
    with open(logfile, 'r') as r:
        tried_zip_list = [int(l.rstrip('\n')) for l in r.readlines()]
    for z in tried_zip_list:
        zip_list.remove(z)
    zip_num_wo_tried = len(zip_list)
    zip_num_diff_2 = zip_num_wo_created - zip_num_wo_tried
    print('{} previously searched zipcodes have no '
          '{} in {}'.format(zip_num_diff_2, establishment, state_code))

    return (zip_list, zip_num_diff_1 + zip_num_diff_2)


def concatenate_zips_for_state(establishment, state_code):

    '''Merges every zipcode CSV for a given place-type and state
    '''

    df = pd.DataFrame(columns=['establishment', 'phone_number', 'address', 'city',
                               'state', 'zipcode', 'website', 'data_source'])
    folder_path = os.path.join('data', establishment, state_code)
    for root, dirs, files in os.walk(folder_path):
        for f in files:
            f_path = os.path.join(folder_path, f)
            temp_df = pd.read_csv(f_path)
            df = pd.concat((df, temp_df))

    df = df.drop_duplicates()
    out_file = os.path.join(folder_path, '{}_all_zipcodes.csv'.format(state_code))
    df.to_csv(out_file, index=False)
    print('Full {} csv for {} created'.format(establishment, state_code))
    
    return


def find_email_addresses(soup, url):

    '''Helper for get_emails(), returns email addresses found on a given website and it's contact page
    '''

    link_list = [a.get('href') for a in soup.find_all('a') if a.get('href') is not None]
    potential_emails = re.findall(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)',
                                  ' '.join(link_list))

    contact_paths = [link for link in link_list if (('contact' in link.lower()))]
    parsed_url = urlparse(url)
    clean_url = '{p.scheme}://{p.netloc}{p.path}'.format(p=parsed_url)
    contact_pages = [''.join((clean_url, c_path)) for c_path in contact_paths]
    contact_pages = list(set(contact_pages))

    for page in contact_pages:
        soup_2 = make_soup(page)
        link_list_2 = [a.get('href') for a in soup.find_all('a')
                       if a.get('href') is not None]
        potential_emails_2 = re.findall(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)',
                                            ' '.join(link_list))
        potential_emails.extend(potential_emails_2)

    set_emails = list(set(potential_emails))
            
    return set_emails


def get_emails(url):

    '''Returns email addresses found on a given website and it's contact page
    '''

    try:
        soup, url = make_soup(url, rtrn_url=True)
        emails = find_email_addresses(soup, url)
    except Exception as e:
        # TODO :: add better error handling
        print(e)
        emails = list()

    return emails



def append_emails_to_copy_of_csv(csv_path, url_column_name='website'):

    '''Creates a copy of the CSV path given "*_with_emails.csv" that includes emails
    '''

    ext_index = csv_path.find('.csv')
    new_path = csv_path[:ext_index] + '_with_emails.csv'
    if os.path.isfile(new_path):
        print('{} already exists'.format(new_path))
        return
    
    else:
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



# MAIN

def grab_data_for_zip(establishment, zipcode, state_code):

    '''Create a csv file containing contact data for a given place-type and zipcode
    '''

    accepted_establishment(establishment)
    accepted_state_code(state_code)

    zipcode = '{:05}'.format(int(zipcode))
    coors = get_coordinates(zipcode)
    if coors:
        place_ids = get_place_ids(establishment,
                                  coors.lat, coors.lng,
                                  coors.rad) if coors else list()
        establishment_data = [get_establishment_data(pid) for pid in place_ids]
        created = write_establishment_data(establishment_data, establishment,
                                           zipcode, state_code)
        if created:
            print('{} csv for zipcode {} created  '.format(establishment, zipcode),
                  end='')
        else:
            print('no {} found for zipcode {}     '.format(establishment, zipcode),
                  end='')
    else:
        print('no {} found for zipcode {}     '.format(establishment, zipcode),
              end='')

    return


def grab_data_for_state(establishment, state_code):

    '''Create a CSV file containing contact data for a given place-type and state
    '''

    state_zip_file = './us_postal_codes.csv'
    df = pd.read_csv(state_zip_file, engine='python')
    zip_list = list(set(df[df['State Abbreviation'] == state_code]['Zip Code']))
    zip_num_all = len(zip_list)
    zip_list, zip_num_diff = check_current_data(zip_list, establishment,
                                                state_code)

    for e, z in enumerate(zip_list):
        grab_data_for_zip(establishment, z, state_code)
        print('|{}/{}|'.format(e + zip_num_diff + 1, zip_num_all))

    concatenate_zips_for_state(establishment, state_code)
    return


def grab_all_data(establishment, state_list):

    '''For each state in the state_list, run method grab_data_for_state()
    '''
    
    for state in state_list:
        try:
            grab_data_for_state(establishment, state)
        except DataFileExistsError:
            print('All {} data from {} already acquired'.format(establishment,
                                                                state))


if __name__ == '__main__':
    print('\n\nThis script will make a csv file of the contact data for '
          'a given type of establishment\nin the given zipcode or state.\n\n'
          'Data will be written to file:\n'
          './[establishment]/[state]/[zipcode].csv\n'
          'If the state option is chosen, a concatenated file will also be '
          'written, to file:\n'
          './[establishment]/[state]/[state]_all_zipcodes.csv\n\n')

    establishment = input('Establishment type?: ').lower()

    state_code = input('Two-letter state code: ').upper()

    answer = input('Search the entire state, or a specific zipcode? '
                       '[(z)ip/(s)tate]: ').lower()
    if answer.startswith('z'):
        zipcode = input('5-digit zipcode: ')
        if not re.match('\d\d\d\d\d', zipcode):
            print('Invalid zipcode\n')
            sys.exit(1)
        print('Working...')
        grab_data_for_zip(establishment, zipcode, state_code)
        print()
        answer = input('Would you like to add related emails? '
                       '[(y)es/(n)o]').lower()
        if answer.startswith('y'):
            csv_file = os.path.join('data', establishment, state_code, zipcode) + '_all_zipcodes.csv'
            append_emails_to_copy_of_csv(csv_file)
        print()
        sys.exit(0)
    elif answer.startswith('s'):
        print('Working...')
        grab_data_for_state(establishment, state_code)
        print()
        answer = input('Would you like to add related emails? '
                       '[(y)es/(n)o]').lower()
        if answer.startswith('y'):      
            csv_file = os.path.join('data', establishment, state_code, zipcode) + '_all_zipcodes.csv'
            append_emails_to_copy_of_csv(csv_file)
        print()
        sys.exit(0)
    else:
        print('Invalid answer\n')
        sys.exit(1)
