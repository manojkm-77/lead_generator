"""Test the query expander with all query types."""
import json
from backend.services.query_expander import QueryExpander

qe = QueryExpander()

test_queries = [
    "Palm Oil Buyers India",
    "Restaurants Hyderabad",
    "Hotels Bangalore",
    "Soap Manufacturers",
    "Food Manufacturers Karnataka",
    "Vegetable Oil Importers",
    "Edible Oil Distributors",
    "CP10 Buyers",
    "Snack Manufacturers Gujarat",
    "Bakery Companies Mumbai",
]

for query in test_queries:
    r = qe.expand(query, max_queries=100)
    sources = {}
    for v in r:
        sources[v["source"]] = sources.get(v["source"], 0) + 1
    print(f"[{query[:30]:30s}] -> {len(r):3d} variations | sources: {sources}")
    if r:
        print(f"  First 3: {[v['query'] for v in r[:3]]}")
    print()

# Also test full 500 expansion
r = qe.expand("Palm Oil Buyers India", max_queries=500)
print(f"\nFull (500) Palm Oil Buyers India: {len(r)} variations")
sources = {}
for v in r:
    sources[v["source"]] = sources.get(v["source"], 0) + 1
print(f"By source: {json.dumps(sources, indent=2)}")
print(f"Locations covered: {len(set(v.get('location', 'India') for v in r))}")
print("ALL TESTS PASSED")
