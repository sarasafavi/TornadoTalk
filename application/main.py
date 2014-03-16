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
        get_addresses = gen.Task(self.get_addresses)
        addresses = yield get_addresses
        logger.info(addresses)
        loc = {"locations": addresses}
        locations = json.dumps(loc)
        geocoded = gen.Task(self.geocode, locations)
        results = yield geocoded
        logger.info("GEOCODED RESULTS: %r", results)
        self.render("templates/map.html", locations=results)
        # nobody should ever do this in the real world
        # delaying client to geocode dozens of addresses on each request?!
        # seriously, paint dries faster than this map will render

    @gen.coroutine
    def get_addresses(self):
        base = ("https://www.googleapis.com/mapsengine/v1/tables/"
                "12421761926155747447-06672618218968397709/features?")
        query = urllib.parse.urlencode({
            "key": gmap_key, "version": "published"})
        url = base + query
        response = yield gen.Task(AsyncHTTPClient().fetch, url)
        dhs_locations = json.loads(response.body.decode("utf-8"))
        addresses = []
        count = 0
        for location in dhs_locations["features"]:
            count += 1
            street = location["properties"]["Street_add"]
            postcode = location["properties"]["Postcode"]
            address = ' '.join([street, postcode])
            addresses.append({"street": address})
            # HACK: tornado times out with 599 after ~20 seconds
            # anything >50 seems to take mapquest >20 seconds to respond
            if count > 40:
                break
        return addresses

    @gen.coroutine
    def geocode(self, locations):
        base = "https://www.mapquestapi.com/geocoding/v1/batch?"
        query = urllib.parse.urlencode({
            "key": urllib.parse.unquote(mapquest_key), "json": locations})
        url = base + query
        logger.info(url)

        client = AsyncHTTPClient()
        response = yield gen.Task(client.fetch, url)
        logger.info("code: %s time: %s body: %s",
                response.code, response.request_time, response.body)
        body = response.body
        decoded = body.decode("utf-8")
        geocoded = json.loads(decoded)
        locations = []
        for result in geocoded["results"]:
            loc = result["locations"][0]  # just use the first match
            latlon = loc["latLng"]
            locations.append(latlon)
        return(locations)


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
