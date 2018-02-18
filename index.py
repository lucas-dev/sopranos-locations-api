#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, 'libs')

import webapp2
import json
from bs4 import BeautifulSoup
from google.appengine.api import urlfetch
import webencodings
import six
import html5lib
import logging

#Controllers
class LocationsHandler(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'   

        # urls
        locations_url = 'https://www.sopranos-locations.com/locations/'
        maps_url = 'https://www.sopranos-locations.com/locations/json/'

        # maps json
        maps_response = urlfetch.fetch(maps_url)
        maps_data = json.loads(maps_response.content)

        # locations page
        locations_response = urlfetch.fetch(locations_url)
        locations_data = locations_response.content
        
        # parsed locations table
        locations_html = BeautifulSoup(locations_data, "html5lib")
        locations_table = locations_html.select('.loctable tbody tr')
        
        # final json output
        json_data = []


        for tr in locations_table:
            td_location_serie = tr.select('td:nth-of-type(1)')
            td_location_life = tr.select('td:nth-of-type(2)')
            td_location_episodes = tr.select('td:nth-of-type(3)')

            # item structure of final json output
            json_row = {'serie': {}, 'life': {}, 'episodes': []}

            # process serie entry
            if len(td_location_serie):
                location_serie = td_location_serie[0]
                location_serie_url = location_serie.find('a')['href']
                location_serie_title = location_serie.find('a'
                        ).text

                slug = location_serie_url.split('/')[2]
                lat = ''
                lon = ''
                for data in maps_data:
                    if data['slug'] == slug:
                        lat = data['lat']
                        lon = data['lng']

                json_row['serie'] = {
                    'url': location_serie_url,
                    'title': location_serie_title,
                    'lat': lat,
                    'lon': lon,
                    }

            
            # process real location entry
            if len(td_location_life):
                location_real_title = td_location_life[0].text
                json_row['life'] = {'title': location_real_title}


            # process episode entry
            if len(td_location_episodes):
                locations_episodes = td_location_episodes[0].select('a')

                if len(locations_episodes):
                    for location_episode in locations_episodes:
                        location_episode_url = location_episode['href']
                        location_episode_title = location_episode['title']
                        location_episode_code = location_episode.text

                        json_row['episodes'].append({'url': location_episode_url,
                                'title': location_episode_title,
                                'code': location_episode_code})


            # append entry to json
            json_data.append(json_row)

        self.response.out.write(json.dumps(json_data))


class LocationHandler(webapp2.RequestHandler):
    def get(self, slug):
        self.response.headers['Content-Type'] = 'application/json'

        location_url = "https://www.sopranos-locations.com/locations/"+slug

        request_location  = urlfetch.fetch(location_url)

        html_data = request_location.content

        location_page = BeautifulSoup(html_data, "html5lib")

        json_data = {"title": "", "description": "", "episodes": [], 
                    "additional_info": "", "lat": "", "lon": "", "images": [], 
                    "closest_locations": []}

        title = location_page.select("#container main h1")
        description = location_page.select("#container p:nth-of-type(2)")
        episodes = location_page.select("#container p:nth-of-type(3) a")
        additional_info = location_page.select("#container p:nth-of-type(4)")
        images = location_page.select(".gallery li > img")
        closest_locations = location_page.select("ol li > a")
        lat = location_page.find_all('div', attrs={'data-lat' : True})[0]
        lon = location_page.find_all('div', attrs={'data-lng' : True})[0]

        json_data["title"] = title[0].text
        json_data["description"] = description[0].text

        for episode in episodes:
          episode_json = {"url": episode["href"], "title": episode.text}  
          json_data["episodes"].append(episode_json)

        for image in images:
          json_data["images"].append(image["srcset"].split(",")[1].split()[0])

        for cl in closest_locations:
          cl_json = {"url": cl["href"], "title": cl.text}
          json_data["closest_locations"].append(cl_json)

        json_data["additional_info"] = additional_info[0].text

        json_data["lat"] = lat['data-lat']
        json_data["lon"] = lon['data-lng']

        self.response.out.write(json.dumps(json_data))


class EpisodesHandler(webapp2.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'application/json'

        NUM_SEASONS = 6

        BASE_SEASON_URL = "https://www.sopranos-locations.com/season-"

        json_data = []

        for season in range(1, NUM_SEASONS+1):
          season_url = BASE_SEASON_URL + str(season)+"/"
          
          request_season  = urlfetch.fetch(season_url)
          html_data = request_season.content
          season_page = BeautifulSoup(html_data, "html5lib")
          
          season_json = {"number": season, "episodes": []}
          
          episodes = season_page.select("#container main > ol > li")
          for episode in episodes:
            season_json["episodes"].append({"url":episode.select("a")[0]["href"], "title":episode.text})
          
          json_data.append(season_json)
          
        self.response.out.write(json.dumps(json_data))


class EpisodeHandler(webapp2.RequestHandler):
    def get(self, season, episode):
        self.response.headers['Content-Type'] = 'application/json'

        episode_url = "https://www.sopranos-locations.com/season-"+season+"/episode-"+episode;

        request_episode  = urlfetch.fetch(episode_url)

        html_data = request_episode.content

        episode_page = BeautifulSoup(html_data, "html5lib")

        json_data = {"title": "", "extra_info_urls": {"imdb":"", "wikipedia": ""}, 
                    "navigation_urls": {"previous":"", "next": ""}, 
                    "locations": []}

        title = episode_page.select("#container main h1")
        extra_info_links = episode_page.select("#container main section > a")
        navigation_links = episode_page.select(".epnav > a")
        locations_list = episode_page.select(".scenelist > li")

        json_data["title"] = title[0].text
        json_data["extra_info_urls"]["imdb"] = extra_info_links[0]["href"]
        json_data["extra_info_urls"]["wikipedia"] = extra_info_links[1]["href"]
        json_data["navigation_urls"]["previous"] = navigation_links[0]["href"]
        json_data["navigation_urls"]["next"] = navigation_links[1]["href"]

        for location in locations_list:
          location_link = location.select("a")
          location_description = location.text.rsplit(".",1)[0]
          location_img = location.select("img")[0]["srcset"].split(",")[1].split()[0]
          location_title = ""
          location_url = ""
          if (len(location_link)):
            location_url = location_link[0]["href"]
            location_title = location_link[0]["title"]
          location_json = {"title":location_title, "description": location_description, 
                            "link": location_url, "img": location_img}
          
          json_data["locations"].append(location_json)

        self.response.out.write(json.dumps(json_data))



# URLS
app = webapp2.WSGIApplication([('/locations', LocationsHandler),
                               ('/location/([^/]+)', LocationHandler),
                               ('/episodes', EpisodesHandler),
                               ('/episode/([^/]+)/([^/]+)', EpisodeHandler)],
                              debug=True)

            