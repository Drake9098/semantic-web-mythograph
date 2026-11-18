"""Namespace e percorsi del progetto."""
from pathlib import Path

from rdflib import Namespace

ROOT = Path(__file__).resolve().parents[2]

MYTH = Namespace("https://example.org/mythograph/ontology#")    # TBox
RES = Namespace("https://example.org/mythograph/resource/")     # individui
GRAPH = Namespace("https://example.org/mythograph/graph/")      # named graph
DCTERMS = Namespace("http://purl.org/dc/terms/")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
FABIO = Namespace("http://purl.org/spar/fabio/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
WD = Namespace("http://www.wikidata.org/entity/")
DBR = Namespace("http://dbpedia.org/resource/")
GEO = Namespace("http://www.w3.org/2003/01/geo/wgs84_pos#")

# Vocabolari esterni a cui MythoGraph si allinea (alignments.ttl)
EXTERNAL_NS = (str(CRM), str(FABIO), str(FOAF))

ONTOLOGY_FILE = ROOT / "ontology" / "mythograph.ttl"
ALIGNMENTS_FILE = ROOT / "ontology" / "alignments.ttl"
SHARED_FILE = ROOT / "data" / "shared.ttl"
LINKS_FILE = ROOT / "data" / "links.ttl"
WIKIDATA_CACHE = ROOT / "data" / "wikidata_cache.json"
SOURCES_DIR = ROOT / "data" / "sources"
OUTPUT_FILE = ROOT / "data" / "generated" / "mythograph.trig"
QUERIES_DIR = ROOT / "queries"

PREFIXES = {
    "myth": MYTH, "res": RES, "g": GRAPH, "dcterms": DCTERMS, "skos": SKOS,
    "crm": CRM, "fabio": FABIO, "foaf": FOAF, "wd": WD, "dbr": DBR, "geo": GEO,
}
