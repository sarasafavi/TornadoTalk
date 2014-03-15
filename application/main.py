import tornado.ioloop
import tornado.web
from tornado.httpclient import AsyncHTTPClient
from tornado import gen
import json
import logging
import urllib.parse
from mysecret import gmap_key, mapquest_key

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
states = {
            "NSW": "New South Whales",
            "QLD": "Queensland",
            "ACT": "Australian Capital Territory",
            "VIC": "Victoria",
            "TAS": "Tasmania",
            "SA": "South Australia"
        }
api_url = "https://www.googleapis.com/mapsengine/v1/tables/12421761926155747447-06672618218968397709/features?version=published&key={0}&where=State='{1}'"


class MainHandler(tornado.web.RequestHandler):
    @gen.coroutine
    def get(self):
        url = "https://www.googleapis.com/mapsengine/v1/tables/12421761926155747447-06672618218968397709/features?version=published&key={0}".format(gmap_key)
        response = yield gen.Task(
            AsyncHTTPClient().fetch,url)

        clean_response = scrub_it(response)

        self.render("templates/main.html",
                    all_locations=clean_response)


class StatesHandler(tornado.web.RequestHandler):
    @gen.coroutine
    def get(self):
        async_client = AsyncHTTPClient()

        output = []
        for k,v in states.items():
            logger.info("Getting {0}".format(k))
            task = gen.Task(self.get_state_data, k, async_client)
            output.append(task)

        results = yield output
        results = dict(results)

        self.render("templates/states.html", **results)

    @gen.coroutine
    def get_state_data(self, state, client):
        url = api_url.format(gmap_key, state)
        output = yield gen.Task(client.fetch, url)
        logger.info("Got {0}".format(state))
        return (state.lower(), scrub_it(output))

class StateHandler(tornado.web.RequestHandler):
    @gen.coroutine
    def get(self, abbv):
        st = abbv.upper()
        url = "https://www.googleapis.com/mapsengine/v1/tables/12421761926155747447-06672618218968397709/features?version=published&key={0}&where=State='{1}'".format(gmap_key, st)
        response = yield gen.Task(
            AsyncHTTPClient().fetch,url)

        clean_response = scrub_it(response)

        self.render("templates/single_state.html",
                    locations=clean_response,
                    name=states[st])

class MapHandler(tornado.web.RequestHandler):

    @gen.coroutine
    def get(self):
        addresses = [{"street":"131 Monaro Street 2620"}]
        loc = {"locations":addresses}
        locations = json.dumps(loc)
        # TODO: parse addresses (street # + locality) out of gmaps api result
        geocoded = gen.Task(self.geocode, locations)
        results = yield geocoded
        logger.info("GEOCODED RESULTS: %r", results)
        self.render("templates/map.html", lat = results[0], lon = results[1],
                foo = [1,2,3,4])

    @gen.coroutine
    def geocode(self, locations):
        # base = "http://nominatim.openstreetmap.org/search.php?"
        # query = urllib.parse.urlencode({"limit":1, "format":"json", "q":address})
        # switch from OSM to mapquest for bulk geocodes
        base = "https://www.mapquestapi.com/geocoding/v1/batch?"
        query = urllib.parse.urlencode(
                    {"key":urllib.parse.unquote(mapquest_key),
                    "json":locations})
        url = base+query
        logger.info(url)
        response = yield gen.Task(AsyncHTTPClient().fetch,url)
        logger.info(response.body)
        geocoded = json.loads(response.body.decode("utf-8"))
        latlon = geocoded["results"][0]["locations"][0]["latLng"]
        lat = latlon['lat']
        lon = latlon['lng']
        return([lat,lon])

def scrub_it(response):
    clean = json.loads(response.body.decode("utf-8"))
    if "features" in clean:
        return clean["features"]
    else:
        return [clean["error"]]



routes = [
    (r"/", MainHandler),
    (r"/states", StatesHandler),
    (r"/state/(.*)", StateHandler),
    (r"/map", MapHandler)
]

application = tornado.web.Application(routes, debug=True)
if __name__ == "__main__":
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
