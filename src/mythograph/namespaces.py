"""Namespace e percorsi del progetto."""
from pathlib import Path

from rdflib import Namespace

ROOT = Path(__file__).resolve().parents[2]

MYTH = Namespace("https://example.org/mythograph/ontology#")    # TBox
RES = Namespace("https://example.org/mythograph/resource/")     # individui
GRAPH = Namespace("https://example.org/mythograph/graph/")      # named graph
MAP = Namespace("https://example.org/mythograph/pipeline#")     # vocabolario delle tabelle di mapping
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

ONTOLOGY_DIR = ROOT / "ontology"
ONTOLOGY_FILE = ONTOLOGY_DIR / "mythograph.ttl"          # core
CONSTRAINTS_FILE = ONTOLOGY_DIR / "constraints.ttl"      # vincoli per singola fonte
SWRL_FILE = ONTOLOGY_DIR / "rules.ttl"                   # regole SWRL
ALIGNMENTS_FILE = ONTOLOGY_DIR / "alignments.ttl"

PIPELINE_DIR = ROOT / "pipeline"                         # query e tabelle della pipeline
RAW_DIR = ROOT / "data" / "raw"                          # passo 1-2: Wikidata grezzo
MAPPED_DIR = ROOT / "data" / "mapped"                    # passo 3: tradotto in myth:
SHARED_FILE = MAPPED_DIR / "shared.ttl"
LINKS_FILE = MAPPED_DIR / "links.ttl"
SOURCES_DIR = MAPPED_DIR / "sources"
OUTPUT_FILE = ROOT / "data" / "generated" / "mythograph.trig"
EXPORTS_DIR = ROOT / "exports"                           # file per Protégé
QUERIES_DIR = ROOT / "queries"

PREFIXES = {
    "myth": MYTH, "res": RES, "g": GRAPH, "dcterms": DCTERMS, "skos": SKOS,
    "crm": CRM, "fabio": FABIO, "foaf": FOAF, "wd": WD, "dbr": DBR, "geo": GEO,
}
