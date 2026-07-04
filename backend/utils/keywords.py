from itertools import product

OIL_TYPES = [
    "Palm Oil", "CP10", "RBD Palm Olein", "Sunflower Oil",
    "Soybean Oil", "Rice Bran Oil", "Canola Oil", "Coconut Oil",
    "Groundnut Oil", "Mustard Oil", "Cooking Oil", "Edible Oil",
]

BUSINESS_TYPES = [
    "Wholesale Oil", "Food Factory", "Snack Manufacturer",
    "Namkeen Manufacturer", "Bakery", "Hotel Supplier",
    "Restaurant Supplier", "Supermarket", "Retail Chain",
    "Wholesale Grocery", "Distributor", "Importer",
]

INDIAN_CITIES = [
    "Mumbai", "Delhi", "Bangalore", "Chennai", "Hyderabad",
    "Kolkata", "Ahmedabad", "Pune", "Jaipur", "Lucknow",
    "Kanpur", "Nagpur", "Indore", "Bhopal", "Visakhapatnam",
    "Coimbatore", "Ludhiana", "Agra", "Nashik", "Vadodara",
]


def generate_search_queries(max_combinations: int = 50) -> list[str]:
    queries = []
    for oil, biz in product(OIL_TYPES[:6], BUSINESS_TYPES[:6]):
        queries.append(f"{oil} {biz} buyer India")
        if len(queries) >= max_combinations:
            break
    return queries


def get_oil_keywords() -> list[str]:
    return OIL_TYPES.copy()


def get_business_keywords() -> list[str]:
    return BUSINESS_TYPES.copy()
