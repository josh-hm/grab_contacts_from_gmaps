# Introduction

I created the code to help with a number of marketing initiatives that required getting the contact details, including emails, for various types of businesses within a postal code.

The python file [grab_contacts_from_gmaps.py](grab_contacts_from_gmaps.py) can be used via a CLI or a Python interpreter to generate a CSV file containing the contact information for all establishments from Google Places for a given postal code.

To use it yourself, you will need to create your own Google API key, access to a CLI, and Python 3.

The Google API key is free, and as of this last update to this file, The Google API key is free, and as of this last update to this file, Google gives you $200 worth of API calls to play around with. (More details in [Managing API limits and charges](#managing-api-limits-and-charges).)

In this repo, I have also included a postal code CSV that will allow you to simply specify a state, and then the code will run through all the postal codes for that state. (Thanks to [aggdata](https://www.aggdata.com/) for the free data!)

## Getting Setup

First, clone this repository.

Second, in whatever environment you want to run the script, you can install any missing packages by running

`pip install -r requirements.txt`

Third, get a Google API key.  If you don't have one, go [here](https://developers.google.com/places/web-service/get-api-key#get_an_api_key) to make your own API key, certify it, and then (for security's sake) restrict it to "Places API" and "Geocoding API".

### Managing API limits and charges 

**This information is only as up-to-date as the last commit to the README.  Please double-check against Google's documentation.**

Since I first wrote this script, Google has changed it's API policies.  Instead of providing free charges until you run out, all users are given $200 worth of API calls per month, but your API key must be associated with a billing account (_i.e._, a way for Google to charge you for overages).  For someone who just wants to play around with the APIs, you need to know how to avoid a big bill from Google.

The easiest fix is to [set API call limits](https://cloud.google.com/apis/docs/capping-api-usage). (**NOTE:** you set limits per day, but charges and limits are per month.). As per the latest info from Google's [documentation](https://cloud.google.com/maps-platform/pricing/sheet/#places), my conservative calculations indicate that the $200 can give you 3,000 monthly calls to the Places API (which includes Places Details and Nearby Search), and up to 300 monthly calls to Geocoding (although you have to run many fewer calls to this API, and it's much cheaper).

The script uses the following API calls:

* [Place Details](https://developers.google.com/places/web-service/details)
* [Nearby Search](https://developers.google.com/places/web-service/search#PlaceSearchRequests)
* [Geocoding](https://developers.google.com/maps/documentation/geocoding/overview)

I highly recommend you check the documentation before you run anything, given that between the time I first made this script and the time I posted it here, the pricing and free usage policies changed.  If you do find a discrepancy between the info here and Google's documentation, I'd greatly appreciate it if you

## Using it

### From CLI

First, change your working directory to the directory where both this script and postal code database are. Then, type:

`python3 grab_contact_info.py`

and then follow the prompts to grab contact info from a single US postal code.  If you want to get the most of out of the CLI experience (powered by [Argparse](https://docs.python.org/3/library/argparse.html)), such as searching multiple postcodes or establishments at once, specifying non-US countries, and more, type:

`python3 grab_contact_info.py -h`

### From Python Interpreter

Load script into your interpreter, and then use one of the following methods:

* `grab_data_for_postal_code(establishment, postal_code, country_code)`
* `grab_data_for_state(establishment, state_code, country_code)`

The methods should accept the establishment types listed in the [Google Places API
documentation](https://developers.google.com/places/web-service/supported_types), the general two-letter state abbreviations for US states, and the two-letter [ISO 3166-1 alpha-2](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2) country codes.  If you input something wrong, there will be a print out of the accepted inputs.

After you create your CSV of contact information, you can append emails scraped from their website and contact page by passing the filepath of the newly created CSV to the following method:

* `append_emails_to_copy_of_csv(csv_path, url_column_name='website')`


### General Run Notes

When querying via postal code, the script uses Google's Geocode API to get the proper Google Places viewwindow coordinates, then Google's Nearby Search to capture place\_id's, and then Google's Place Details to get the contact details.  To append emails, the script runs through the created CSV's _website_ column, uses [Requests](https://requests.readthedocs.io/en/master/) and [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) to scrape all the emails from the given website (and it's contact page, if found).

When querying via state, the script looks through the provide postal code CSV to enumerate through postal codes of the given state.

If an error occurs when attempting to access the Places or Geocoding API, the status code and URL for the Google API will be printed, and an ApiStatusError will be thrown.

I have not implemented proper error handling for the email scraping part of the script.  At the moment it simply catches and prints the error, skipping the website where it encountered the error when trying to find emails.

Related, I am in the middle of creating unit tests, so there could very well be a bug or two that screws up your data collection.  If you run into any bugs &mdash; sorry! &mdash; please reach out and let me know.


## Data files and logging behavior

Data and log files will be created in the same directory as this repository.

The "logfile" will keep track of the postal codes that have been searched
and do not contain any of the specified establishment.

File structure works as follows

```
repository/
|
.
.
.
|---+data/
    |
    |---+[establishment]/
        |
        |---+[country_code]/
            |
            |---[postal_code].csv
            |---[postal_code]_with_emails.csv
            |---[state_code]_all_postal_codes.csv
            |---[state_code]_all_postal_codes_with_emails.csv
            |   
            |---+logs/
	        |
	        |---logfile
```
