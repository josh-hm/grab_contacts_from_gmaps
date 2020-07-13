# Introduction

I created the code to help with a number of marketing initiatives
that required getting the contact details for various types of
businesses within a certain area.

The python file *grab\_contacts\_from\_gmaps.py* can be used via a CLI
or a Python interpretor to generate a CSV file containing the contact
information for all establishments from Google Places for a given US
state or zipcode.

To use it yourself, you will need to create your own Google API key,
access to a CLI, and Python 3.

The Google API key is free and will give you a fair number of free
calls per day, such that you should be able to grab many contacts from
a given state (or all from a given zipode) for various types of
establishments.

In this repo, I have also included a state--zipcode CSV that will
allow you to simply specify a state, and then the code will run
through all the zipcodes for that state. (Thanks to
[aggdata](https://www.aggdata.com/) for the free data!)

## Getting Setup

First, clone this repository.

Second, in whatever environment you want to run the script, you can
install any missing packages by running

`pip install -r requirements.txt`

Third, get a Google API key.  If you don't have one, go
[here](https://developers.google.com/places/web-service/get-api-key#get_an_api_key)
to make your own API key, certify it, and then enable "Google Places
API Web Services" and "Google Maps Geocoding API".


## Using it

### From CLI

First, change your working directory to the directory where
both this script and zipcode database are. Then, type

`python grab_contact_info.py`

and then simply follow the prompts.

### From Python Interpretor

Load script into your interpretor, and then use one of the following methods:

* *grab\_data\_for\_zip(establishment, zipcode, state_code)*
* *grab\_data\_for\_state(establishment, state_code)*
* *grab\_all\_data(establishment, state_list)*

The method should accept the establishment types listed in the [Google
Places API
documentation](https://developers.google.com/places/web-service/supported_types),
and the general state abbreviations for US states.  If you input
something wrong, the methods will print out the list of accepted inputs.


### General Run Notes

When querying via zipcode, the script uses Google's Geocode API to get the
proper Google Places viewwindow coordinates.

When querying via state, the script looks through the provide
state--zipcode CSV to enumerate through zipcodes of the given state.

If an error occurs when attempting to access the Places or Geocoding
API, the status code and URL for the Google API will be printed, and
an ApiStatusError will be thrown.


## Data files and logging behavior

Data and log files will be created in the same directory as this repository.

The "logfile" will keep track of the zipcodes that have been searched
and do not contain any of the specified establishment.

File structure works as follows

```
repository/
|
.
.
.
|
|---+data/
    |
    |
    |---+[establishment]/
    |   |
    |   |---+[state_code]/
    |       |
    |       |---[zip_code].csv
    |       |---[state_code]_all_zipcodes.csv
    |   
    |
    |---+logs/
	|
	|---+[state_code]/
	    |
	    |---logfile
```