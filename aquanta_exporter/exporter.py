import argparse
import http.server
import logging
import sys

import prometheus_client

import aquanta_exporter


def main():
    parser = argparse.ArgumentParser("Aquanta Exporter")

    parser.add_argument("--verbose", "-v", action="count")
    parser.add_argument("--port", type=int, default=4577)
    parser.add_argument("--bind_address", default="0.0.0.0")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)

    args = parser.parse_args()

    if args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(stream=sys.stdout, level=level)

    collector = aquanta_exporter.AquantaCollector(args.username, args.password)

    prometheus_client.REGISTRY.register(collector)

    handler = prometheus_client.MetricsHandler.factory(
            prometheus_client.REGISTRY)
    server = http.server.HTTPServer(
            (args.bind_address, args.port), handler)
    server.serve_forever()
