"""
BuyerHunter AI — Massive Query Expansion Engine v3

Generates thousands of intelligent search variations from ANY user query.
Handles: products, industries, services, business types, locations.
Expands across every Indian state, district, and major city.
"""

import logging
import re
from itertools import product as cartesian_product

logger = logging.getLogger(__name__)

# ── Query Type Detection ─────────────────────────────────────────────────────
QUERY_TYPES = {
    "product_buyer": r"(palm oil|cp10|cp8|edible oil|cooking oil|vegetable oil|sunflower oil|refined oil|vanaspati|soap|detergent|chemical|raw material|ingredient).*(buyer|purchaser|importer|procurement)",
    "product_manufacturer": r"(palm oil|cp10|cp8|edible oil|soap|detergent|food|snack|bakery|chocolate|candy|cosmetic|personal care|chemical).*(manufacturer|maker|producer|factory)",
    "product_distributor": r"(palm oil|edible oil|cooking oil|food|soap|chemical).*(distributor|wholesaler|dealer|supplier|stockist)",
    "industry_search": r"(food|bakery|snack|soap|detergent|cosmetic|pharma|chemical|textile|plastic|auto|steel|cement|paper|rubber|packaging) (manufacturer|company|factory|industry|producer|maker)",
    "service_search": r"(restaurant|hotel|hospital|school|college|cafe|bakery|cloud kitchen|catering|canteen|gym|salon|spa)",
    "location_search": r"(in |of )?(mumbai|delhi|bangalore|hyderabad|chennai|kolkata|pune|ahmedabad|surat|jaipur)",
    "import_export": r"(importer|exporter|import|export|trade|trading).*(india|overseas|international)",
}

# ── Product & Service Synonyms (massive expansion) ──────────────────────────
PRODUCT_SYNONYMS = {
    "palm oil": ["palm oil", "crude palm oil", "CPO", "palm olein", "RBD palm olein",
                 "CP10", "CP8", "CP6", "palm stearin", "palm kernel oil", "PKO",
                 "palm fraction", "palm mid fraction", "palm fatty acid", "PFAD",
                 "refined palm oil", "bleached palm oil", "deodorized palm oil",
                 "palm oil refined", "edible palm oil", "food grade palm oil"],
    "cp10": ["CP10", "RBD palm olein", "palm olein", "palm oil", "refined palm olein",
             "cooking oil palm", "palm cooking oil"],
    "cp8": ["CP8", "RBD palm olein", "palm olein", "palm oil", "refined palm olein"],
    "rbd palm olein": ["RBD palm olein", "palm olein", "CP10", "CP8", "palm oil",
                       "refined bleached deodorized palm olein"],
    "palm stearin": ["palm stearin", "palm stearine", "hard palm oil",
                     "palm fat", "solid palm oil"],
    "palm kernel oil": ["palm kernel oil", "PKO", "palm kernel", "kernel oil"],
    "sunflower oil": ["sunflower oil", "refined sunflower oil", "sunflower refined oil",
                      "sun oil", "sunflower refined", "sunflower cooking oil",
                      "kisan sunflower oil", "sunlite oil"],
    "soybean oil": ["soybean oil", "soya oil", "refined soybean oil", "soy oil",
                    "soyabean oil", "refined soya oil", "soya bean oil",
                    "degummed soybean oil", "crude soybean oil"],
    "mustard oil": ["mustard oil", "mustard seed oil", "sarson oil", "kachi ghani mustard oil",
                    "pure mustard oil", "mustard cooking oil"],
    "groundnut oil": ["groundnut oil", "peanut oil", "moongfali oil", "groundnut refined oil",
                      "peanut cooking oil"],
    "coconut oil": ["coconut oil", "copra oil", "coconut refined oil", "pure coconut oil",
                    "virgin coconut oil", "coconut cooking oil", "coconut oil edible"],
    "rice bran oil": ["rice bran oil", "rice bran refined oil", "rice bran cooking oil",
                      "rice oil"],
    "cottonseed oil": ["cottonseed oil", "cotton seed oil", "cotton oil"],
    "vegetable oil": ["vegetable oil", "refined vegetable oil", "vanaspati",
                      "vegetable ghee", "cooking oil", "edible oil", "mixed vegetable oil",
                      "vegetable fat", "vegetable shortening"],
    "cooking oil": ["cooking oil", "edible oil", "vegetable oil", "refined oil",
                    "frying oil", "deep fry oil", "cooking medium", "frying medium",
                    "industrial cooking oil", "bulk cooking oil"],
    "edible oil": ["edible oil", "cooking oil", "vegetable oil", "refined oil",
                   "refined edible oil", "food grade oil", "edible vegetable oil",
                   "edible refined oil", "pure edible oil"],
    "refined oil": ["refined oil", "refined edible oil", "refined vegetable oil",
                    "refined cooking oil", "RBD oil", "refined bleached deodorized oil"],
    "vanaspati": ["vanaspati", "vanaspati oil", "vegetable ghee", "hydrogenated oil",
                  "partially hydrogenated", "vanaspati ghee", "dalda", "rath vanaspati",
                  "hydrogenated vegetable oil"],
    "shortening": ["shortening", "baking shortening", "cake margarine",
                   "industrial margarine", "pastry margarine", "puff pastry shortening",
                   "all purpose shortening", "vegetable shortening"],
    "bakery fat": ["bakery fat", "bakery margarine", "baking fat",
                   "puff pastry margarine", "bread fat", "cake fat",
                   "bakery shortening", "industrial bakery fat"],
    "margarine": ["margarine", "table margarine", "industrial margarine",
                  "bakery margarine", "soft margarine", "butter substitute"],
    "frying oil": ["frying oil", "deep frying oil", "industrial frying oil",
                   "frying medium", "industrial frying medium", "frying fat"],
    "soap": ["soap", "toilet soap", "bath soap", "laundry soap", "washing soap",
             "hand wash", "body wash", "cleansing bar", "soap bar", "glycerine soap",
             "transparent soap", "herbal soap", "ayurvedic soap", "beauty soap",
             "soap noodles", "soap base", "soap manufacturer"],
    "detergent": ["detergent", "detergent powder", "detergent cake", "detergent bar",
                  "liquid detergent", "washing powder", "laundry detergent",
                  "dishwash", "dishwashing liquid", "floor cleaner", "cleaning powder",
                  "household detergent", "industrial detergent"],
    "hand wash": ["hand wash", "hand sanitizer", "liquid hand wash", "hand soap",
                  "antibacterial hand wash"],
    "cosmetic": ["cosmetic", "cosmetics", "personal care", "beauty products",
                 "skin care", "hair care", "body lotion", "cream", "lotion",
                 "face cream", "fairness cream", "sunscreen", "makeup",
                 "lipstick", "eye shadow", "foundation", "compact powder"],
    "skin care": ["skin care", "face cream", "body lotion", "moisturizer",
                  "anti aging cream", "sunscreen", "face wash", "skin care products"],
    "hair care": ["hair care", "shampoo", "hair oil", "hair conditioner",
                  "hair cream", "hair gel", "hair color", "hair dye"],
    "food": ["food", "food products", "food processing", "food manufacturer",
             "packaged food", "processed food", "food processing company",
             "food industry", "food factory", "food business"],
    "bakery": ["bakery", "bakery products", "bread", "biscuit", "cookies",
               "cakes", "pastry", "rusk", "bakery items", "bun", "pav",
               "bakery manufacturer", "bakery factory", "baking industry"],
    "biscuit": ["biscuit", "biscuits", "cookie", "cookies", "biscuit manufacturer",
                "biscuit factory", "cream biscuit", "digestive biscuit"],
    "snack": ["snack", "snacks", "namkeen", "chips", "wafers", "extruded snacks",
              "fried snacks", "packaged snacks", "namkeen manufacturer",
              "snack food", "munchies", "bhujia", "mixture", "chewda"],
    "namkeen": ["namkeen", "namkin", "bhujia", "mixture", "chanachur",
                "namkeen manufacturer", "traditional snacks"],
    "chips": ["chips", "potato chips", "wafers", "tortilla chips", "corn chips",
              "snack chips", "french fries", "frozen fries"],
    "chocolate": ["chocolate", "chocolate manufacturer", "chocolate factory",
                  "cocoa", "compound chocolate", "dark chocolate", "milk chocolate",
                  "white chocolate", "chocolate bar", "cocoa butter"],
    "confectionery": ["confectionery", "chocolate", "candy", "toffee", "sweets",
                      "mints", "gummies", "hard candy", "lollipop", "caramel",
                      "confectionery manufacturer", "sugar confectionery"],
    "ice cream": ["ice cream", "icecream", "frozen dessert", "ice cream manufacturer",
                  "ice cream factory", "frozen yogurt", "kulfi", "gelato"],
    "noodle": ["noodle", "noodles", "instant noodles", "pasta", "macaroni",
               "vermicelli", "noodle manufacturer", "pasta manufacturer"],
    "baby food": ["baby food", "infant food", "baby cereal", "baby formula",
                  "baby snacks", "baby food manufacturer"],
    "dairy": ["dairy", "dairy products", "milk", "butter", "ghee", "paneer",
              "cheese", "yogurt", "curd", "buttermilk", "dairy factory",
              "dairy farm", "milk processing", "dairy industry"],
    "ghee": ["ghee", "clarified butter", "pure ghee", "cow ghee", "buffalo ghee",
             "desi ghee", "ghee manufacturer", "ghee supplier"],
    "meat": ["meat", "meat processing", "chicken", "mutton", "pork", "beef",
             "meat products", "frozen meat", "meat processing plant"],
    "seafood": ["seafood", "fish", "shrimp", "prawn", "frozen fish", "fish processing",
                "seafood exporter", "marine products", "fishery"],
    "beverage": ["beverage", "beverages", "soft drink", "juice", "cold drink",
                 "carbonated drink", "energy drink", "packaged water", "mineral water",
                 "beverage manufacturer", "drink manufacturer"],
    "juice": ["juice", "fruit juice", "packaged juice", "fresh juice",
              "juice manufacturer", "juice concentrate"],
    "animal feed": ["animal feed", "poultry feed", "cattle feed", "fish feed",
                    "livestock feed", "dairy feed", "feed manufacturing",
                    "animal feed manufacturer", "feed mill", "feed factory"],
    "poultry feed": ["poultry feed", "chicken feed", "broiler feed", "layer feed",
                     "poultry feed manufacturer", "feed supplement"],
    "pharmaceutical": ["pharmaceutical", "pharma", "medicine", "drug", "tablet",
                       "capsule", "pharmaceutical company", "pharma manufacturer",
                       "drug manufacturer", "ayurvedic medicine", "herbal product"],
    "ayurvedic": ["ayurvedic", "ayurveda", "herbal", "herbal product", "ayurvedic medicine",
                  "ayurvedic company", "natural product", "herbal supplement"],
    "nutraceutical": ["nutraceutical", "health supplement", "dietary supplement",
                      "protein powder", "vitamin", "nutritional supplement",
                      "health drink", "wellness product"],
    "chemical": ["chemical", "industrial chemical", "chemical manufacturer",
                 "specialty chemical", "fine chemical", "petrochemical",
                 "chemical industry", "chemical factory"],
    "oleochemical": ["oleochemical", "oleo chemical", "fatty acid", "glycerine",
                     "glycerol", "stearic acid", "oleic acid", "fatty alcohol",
                     "oleochemical manufacturer"],
    "surfactant": ["surfactant", "surface active agent", "detergent raw material",
                   "LABSA", "SLES", "SLS", "sulfonic acid"],
    "packaging": ["packaging", "packaging material", "packaging company",
                  "packaging manufacturer", "flexible packaging", "rigid packaging",
                  "plastic packaging", "paper packaging", "corrugated box",
                  "carton box", "packaging industry"],
    "plastic": ["plastic", "plastic product", "plastic manufacturer",
                "plastic molding", "injection molding", "plastic industry",
                "plastic factory", "PET", "HDPE", "LDPE", "PP"],
    "paper": ["paper", "paper manufacturer", "paper mill", "paper product",
              "paper industry", "printing paper", "packaging paper", "kraft paper"],
    "textile": ["textile", "textile manufacturer", "textile mill", "fabric",
                "garment", "apparel", "clothing", "textile industry",
                "cotton textile", "synthetic fabric", "yarn", "thread"],
    "garment": ["garment", "readymade garment", "apparel", "clothing manufacturer",
                "garment factory", "garment manufacturing", "fashion"],
    "leather": ["leather", "leather product", "leather manufacturer", "leather goods",
                "leather footwear", "leather industry", "tannery"],
    "rubber": ["rubber", "rubber product", "rubber manufacturer", "rubber industry",
               "rubber goods", "tyre", "tire", "rubber factory"],
    "steel": ["steel", "steel manufacturer", "steel plant", "steel industry",
              "steel product", "mild steel", "stainless steel", "alloy steel",
              "TMT bar", "steel pipe"],
    "cement": ["cement", "cement manufacturer", "cement factory", "cement industry",
               "ready mix concrete", "RMC", "cement plant"],
    "automobile": ["automobile", "auto", "automotive", "auto parts", "auto manufacturer",
                   "car manufacturer", "auto component", "automobile industry",
                   "vehicle manufacturer", "auto ancillary"],
    "auto parts": ["auto parts", "auto components", "auto spare parts",
                   "automotive parts", "car parts", "bike parts"],
    "electronics": ["electronics", "electronic product", "electronic manufacturer",
                    "electronic industry", "electronic component", "consumer electronics",
                    "electrical manufacturer", "electrical industry"],
    "electrical": ["electrical", "electrical product", "electrical manufacturer",
                   "electrical equipment", "switchgear", "cable", "wire",
                   "transformer", "electric motor", "electrical industry"],
    "solar": ["solar", "solar panel", "solar energy", "solar manufacturer",
              "solar product", "solar inverter", "solar system", "renewable energy"],
    "paint": ["paint", "paint manufacturer", "paint industry", "coating",
              "industrial paint", "emulsion paint", "enamel paint", "paint factory"],
    "furniture": ["furniture", "furniture manufacturer", "furniture factory",
                  "home furniture", "office furniture", "wooden furniture",
                  "modular furniture", "furniture industry"],
    "restaurant": ["restaurant", "fine dining", "casual dining", "restaurant chain",
                   "family restaurant", "multi cuisine restaurant", "pure veg restaurant",
                   "non veg restaurant", "dhaba", "food court", "eatery"],
    "hotel": ["hotel", "hotel chain", "luxury hotel", "boutique hotel", "business hotel",
              "resort", "budget hotel", "heritage hotel", "motel", "inn",
              "guest house", "homestay", "hotel and resort"],
    "cloud kitchen": ["cloud kitchen", "dark kitchen", "ghost kitchen", "virtual kitchen",
                      "food delivery kitchen", "online kitchen"],
    "catering": ["catering", "caterer", "catering service", "event catering",
                 "wedding caterer", "corporate catering", "industrial catering"],
    "hospital": ["hospital", "nursing home", "clinic", "medical center",
                 "multi specialty hospital", "super specialty hospital",
                 "healthcare", "diagnostic center", "pathology lab"],
    "agriculture": ["agriculture", "farming", "agro", "agricultural product",
                    "farm", "organic farming", "agriculture industry",
                    "agro processing", "food grain", "spice", "pulses", "grains"],
    "spice": ["spice", "spices", "masala", "spice manufacturer", "spice grinding",
              "turmeric", "chilli powder", "garam masala", "mixed masala",
              "spice powder", "whole spice"],
    "tea": ["tea", "tea manufacturer", "tea garden", "tea estate", "tea processing",
            "packaged tea", "green tea", "black tea", "CTC tea", "orthodox tea"],
    "coffee": ["coffee", "coffee manufacturer", "coffee processing", "coffee roaster",
               "instant coffee", "filter coffee", "coffee bean", "coffee powder"],
    "sugar": ["sugar", "sugar manufacturer", "sugar mill", "sugar refinery",
              "sugar industry", "milled sugar", "powdered sugar"],
    "rice": ["rice", "rice mill", "rice manufacturer", "basmati rice", "non basmati rice",
             "rice processing", "rice industry", "rice exporter", "parboiled rice"],
    "wheat flour": ["wheat flour", "atta", "maida", "flour mill", "wheat flour manufacturer",
                    "chakki atta", "whole wheat flour", "refined flour"],
    "organic": ["organic", "organic product", "organic food", "organic company",
                "organic farming", "organic certification", "organic manufacturer"],
    "FMCG": ["FMCG", "fast moving consumer goods", "fmcg company", "consumer goods",
             "packaged goods", "consumer product", "fmcg manufacturer"],
    "supermarket": ["supermarket", "hypermarket", "retail store", "grocery store",
                    "department store", "mini mart", "convenience store",
                    "retail chain", "supermarket chain"],
    "retail": ["retail", "retailer", "retail chain", "retail store", "retail shop",
               "retail business", "retail industry", "kirana store", "general store"],
}

# ── Industry Verticals (for industry-type queries) ──────────────────────────
INDUSTRY_VERTICALS = [
    "food manufacturer", "snack manufacturer", "bakery", "bakery manufacturer",
    "biscuit manufacturer", "cookie manufacturer", "cracker manufacturer",
    "confectionery manufacturer", "chocolate factory", "chocolate manufacturer",
    "ice cream manufacturer", "ice cream factory", "frozen dessert manufacturer",
    "namkeen manufacturer", "wafers manufacturer", "chips manufacturer",
    "noodle manufacturer", "pasta manufacturer", "instant food manufacturer",
    "packaged food company", "food processing company", "food factory",
    "sweet manufacturer", "mithai shop", "dessert company",
    "dairy", "dairy products", "dairy factory", "milk processing plant",
    "ghee manufacturer", "butter manufacturer", "cheese manufacturer",
    "soap manufacturer", "soap factory", "detergent manufacturer",
    "cleaning products company", "household products manufacturer",
    "cosmetic manufacturer", "cosmetics factory", "personal care company",
    "hair care company", "skin care company", "beauty products manufacturer",
    "edible oil manufacturer", "oil refinery", "oil mill", "oil processing unit",
    "vanaspati manufacturer", "shortening manufacturer", "margarine manufacturer",
    "oleochemical manufacturer", "fatty acid manufacturer", "glycerine manufacturer",
    "restaurant", "restaurant chain", "fine dining restaurant", "casual dining",
    "cloud kitchen", "catering company", "caterer",
    "hotel", "hotel chain", "resort", "luxury hotel", "boutique hotel",
    "institutional catering", "canteen", "food service",
    "animal feed manufacturer", "feed mill", "poultry feed manufacturer",
    "poultry farm", "dairy farm", "fishery", "fish processing",
    "pharmaceutical company", "pharma manufacturer", "ayurvedic company",
    "herbal product manufacturer", "nutraceutical company",
    "chemical manufacturer", "chemical factory", "specialty chemical",
    "packaging manufacturer", "packaging company", "packaging industry",
    "plastic manufacturer", "plastic product manufacturer",
    "FMCG company", "FMCG manufacturer", "consumer goods company",
    "supermarket", "retail chain", "department store", "grocery store",
    "hospital", "nursing home", "diagnostic center", "healthcare provider",
    "hotel and restaurant supply", "food service equipment",
]

# ── Business Type Patterns (search suffixes) ────────────────────────────────
BUSINESS_TYPES = {
    "buyers": ["buyer", "purchaser", "procurement", "buyer of", "purchase",
               "requirement of", "need of", "looking for"],
    "importers": ["importer", "import agent", "trading company", "import house",
                  "import firm", "overseas buyer", "international buyer"],
    "exporters": ["exporter", "export house", "trading company", "export agent",
                  "export firm", "overseas supplier", "international supplier"],
    "manufacturers": ["manufacturer", "producer", "factory", "refinery",
                      "manufacturing company", "manufacturing unit",
                      "processing unit", "production unit", "maker"],
    "distributors": ["distributor", "distribution company", "supply chain",
                     "distributor of", "authorized distributor",
                     "stockist", "dealer", "channel partner"],
    "wholesalers": ["wholesaler", "wholesale dealer", "bulk supplier",
                    "wholesale market", "wholesale trader",
                    "bulk seller", "wholesale distributor"],
    "retailers": ["retailer", "retail chain", "store", "supermarket",
                  "hypermarket", "retail shop", "kirana store",
                  "convenience store", "department store"],
    "suppliers": ["supplier", "vendor", "provider", "supplier of",
                  "vendor for", "raw material supplier"],
    "processors": ["processor", "refiner", "milling", "processing unit",
                   "processing plant", "processing facility"],
    "traders": ["trader", "trading", "commodity trader", "oil trader",
                "commodity trading", "trading firm", "merchant"],
    "services": ["services", "service provider", "contractor",
                 "service company", "service industry"],
}

# ── Indian Locations (comprehensive) ────────────────────────────────────────
INDIAN_STATES_CITIES = {
    "Andhra Pradesh": ["Visakhapatnam", "Vijayawada", "Guntur", "Nellore", "Kurnool",
                       "Rajahmundry", "Tirupati", "Kakinada", "Anantapur", "Kadapa",
                       "Chittoor", "Machilipatnam", "Tenali", "Ongole"],
    "Arunachal Pradesh": ["Itanagar", "Naharlagun", "Pasighat", "Tawang"],
    "Assam": ["Guwahati", "Silchar", "Dibrugarh", "Jorhat", "Nagaon", "Tinsukia",
              "Tezpur", "Bongaigaon", "Barpeta"],
    "Bihar": ["Patna", "Gaya", "Muzaffarpur", "Bhagalpur", "Darbhanga", "Purnia",
              "Bihar Sharif", "Arrah", "Begusarai", "Katihar", "Sasaram", "Hajipur"],
    "Chhattisgarh": ["Raipur", "Bhilai", "Bilaspur", "Korba", "Durg", "Rajnandgaon",
                     "Raigarh", "Ambikapur"],
    "Goa": ["Panaji", "Margao", "Vasco da Gama", "Mapusa", "Ponda", "Old Goa"],
    "Gujarat": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Bhavnagar", "Jamnagar",
                "Junagadh", "Gandhinagar", "Anand", "Nadiad", "Morbi", "Mehsana",
                "Bharuch", "Navsari", "Bhuj", "Gandhidham", "Valsad", "Palanpur",
                "Porbandar", "Surendranagar"],
    "Haryana": ["Gurugram", "Faridabad", "Panipat", "Karnal", "Ambala", "Hisar",
                "Rohtak", "Sonipat", "Yamunanagar", "Panchkula", "Bhiwani",
                "Rewari", "Sirsa", "Kurukshetra"],
    "Himachal Pradesh": ["Shimla", "Mandi", "Dharamshala", "Solan", "Kullu", "Manali",
                         "Palampur", "Hamirpur", "Bilaspur", "Una"],
    "Jharkhand": ["Ranchi", "Jamshedpur", "Dhanbad", "Bokaro", "Deoghar", "Hazaribagh",
                  "Giridih", "Ramgarh", "Dumka"],
    "Karnataka": ["Bengaluru", "Mysuru", "Hubli", "Mangaluru", "Belgaum", "Davangere",
                  "Bellary", "Shimoga", "Tumkur", "Udupi", "Hassan", "Raichur",
                  "Dharwad", "Gadag", "Hospet", "Gulbarga"],
    "Kerala": ["Thiruvananthapuram", "Kochi", "Kozhikode", "Thrissur", "Malappuram",
               "Kollam", "Alappuzha", "Palakkad", "Kannur", "Kasaragod", "Kottayam",
               "Pathanamthitta", "Idukki", "Wayanad"],
    "Madhya Pradesh": ["Bhopal", "Indore", "Jabalpur", "Gwalior", "Ujjain", "Sagar",
                       "Dewas", "Satna", "Ratlam", "Rewa", "Mandsaur", "Burhanpur",
                       "Khandwa", "Chhindwara", "Itarsi"],
    "Maharashtra": ["Mumbai", "Pune", "Nagpur", "Thane", "Nashik", "Aurangabad",
                    "Solapur", "Kolhapur", "Amravati", "Navi Mumbai", "Kalyan",
                    "Vasai-Virar", "Panvel", "Chandrapur", "Jalgaon", "Akola",
                    "Latur", "Ahmednagar", "Dhule", "Nanded", "Sangli", "Satara",
                    "Ratnagiri", "Wardha", "Bhiwandi", "Malegaon"],
    "Manipur": ["Imphal", "Bishnupur", "Thoubal"],
    "Meghalaya": ["Shillong", "Tura", "Nongstoin"],
    "Mizoram": ["Aizawl", "Lunglei", "Champhai"],
    "Nagaland": ["Kohima", "Dimapur", "Mokokchung", "Tuensang"],
    "Odisha": ["Bhubaneswar", "Cuttack", "Rourkela", "Berhampur", "Sambalpur",
               "Puri", "Balasore", "Bhadrak", "Baripada", "Jharsuguda"],
    "Punjab": ["Ludhiana", "Amritsar", "Jalandhar", "Patiala", "Bathinda",
               "Mohali", "Pathankot", "Hoshiarpur", "Batala", "Moga",
               "Barnala", "Firozpur", "Kapurthala", "Phagwara"],
    "Rajasthan": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer", "Bikaner",
                  "Bhilwara", "Alwar", "Bharatpur", "Sikar", "Pali", "Sri Ganganagar",
                  "Kishangarh", "Tonk", "Beawar", "Chittorgarh", "Hanumangarh"],
    "Sikkim": ["Gangtok", "Namchi", "Gyalshing"],
    "Tamil Nadu": ["Chennai", "Coimbatore", "Madurai", "Salem", "Tiruchirappalli",
                   "Tiruppur", "Erode", "Vellore", "Thoothukkudi", "Dindigul",
                   "Ranipet", "Kancheepuram", "Karaikudi", "Nagercoil",
                   "Tirunelveli", "Hosur", "Ooty", "Kumbakonam", "Cuddalore"],
    "Telangana": ["Hyderabad", "Warangal", "Nizamabad", "Karimnagar", "Khammam",
                  "Ramagundam", "Mahbubnagar", "Adilabad", "Suryapet", "Miryalaguda",
                  "Siddipet", "Jagtial"],
    "Tripura": ["Agartala", "Udaipur", "Dharmanagar"],
    "Uttar Pradesh": ["Lucknow", "Noida", "Varanasi", "Kanpur", "Agra", "Meerut",
                      "Ghaziabad", "Prayagraj", "Bareilly", "Aligarh", "Moradabad",
                      "Gorakhpur", "Saharanpur", "Mathura", "Ayodhya", "Jhansi",
                      "Firozabad", "Muzaffarnagar", "Rampur", "Etawah",
                      "Hapur", "Loni", "Shahjahanpur", "Bulandshahr"],
    "Uttarakhand": ["Dehradun", "Haridwar", "Haldwani", "Rishikesh", "Roorkee",
                    "Rudrapur", "Kashipur", "Nainital", "Mussoorie"],
    "West Bengal": ["Kolkata", "Howrah", "Durgapur", "Siliguri", "Asansol",
                    "Bardhaman", "Malda", "Haldia", "Kharagpur", "Darjeeling",
                    "Krishnanagar", "Jalpaiguri", "Balurghat", "Basirhat",
                    "English Bazar", "Baharampur", "Habra", "Kanchrapara"],
    "Delhi": ["New Delhi", "Dwarka", "Rohini", "Janakpuri", "Saket", "Lajpat Nagar",
              "Karol Bagh", "Connaught Place", "South Extension", "Pitampura",
              "Shahdara", "Najafgarh", "Narela"],
    "Puducherry": ["Puducherry", "Karaikal", "Yanam", "Mahe"],
    "Jammu & Kashmir": ["Srinagar", "Jammu", "Anantnag", "Baramulla", "Sopore",
                        "Kathua", "Udhampur", "Rajouri"],
    "Ladakh": ["Leh", "Kargil"],
}

ALL_STATES = list(INDIAN_STATES_CITIES.keys())

ALL_CITIES = []
for cities in INDIAN_STATES_CITIES.values():
    ALL_CITIES.extend(cities)

# ── Source Definitions (adapter-style) ──────────────────────────────────────
SOURCE_DEFINITIONS = {
    "indiamart": {
        "name": "IndiaMART",
        "type": "b2b_directory",
        "url_pattern": "https://www.indiamart.com/search.html?ss={query}&src=se",
        "priority": 10,
        "max_pages": 5,
        "delay": 2,
        "description": "India's largest B2B marketplace",
    },
    "justdial": {
        "name": "JustDial",
        "type": "local_directory",
        "url_pattern": "https://www.justdial.com/{city}/{query}",
        "priority": 9,
        "max_pages": 3,
        "delay": 3,
        "description": "Local business directory",
    },
    "tradeindia": {
        "name": "TradeIndia",
        "type": "b2b_directory",
        "url_pattern": "https://www.tradeindia.com/search.html?keyword={query}",
        "priority": 8,
        "max_pages": 5,
        "delay": 2,
        "description": "B2B trade directory",
    },
    "yellowpages": {
        "name": "Yellow Pages India",
        "type": "local_directory",
        "url_pattern": "https://www.yellowpages.in/search?search_text={query}",
        "priority": 7,
        "max_pages": 3,
        "delay": 2,
        "description": "Business directory",
    },
    "exportersindia": {
        "name": "ExportersIndia",
        "type": "trade_directory",
        "url_pattern": "https://www.exportersindia.com/search.html?ss={query}",
        "priority": 8,
        "max_pages": 5,
        "delay": 2,
        "description": "Import-export business directory",
    },
    "google": {
        "name": "Google Search",
        "type": "web_search",
        "url_pattern": "https://www.google.com/search?q={query}&num=10",
        "priority": 6,
        "max_pages": 3,
        "delay": 1,
        "description": "General web search",
    },
    "google_maps": {
        "name": "Google Maps",
        "type": "local_directory",
        "url_pattern": "https://www.google.com/maps/search/{query}",
        "priority": 7,
        "max_pages": 3,
        "delay": 3,
        "description": "Business listings on Google Maps",
    },
}


class QueryExpander:
    """Massive query expansion engine. Handles ANY query type."""

    def expand(self, query: str, max_queries: int = 500) -> list[dict]:
        """
        Expand a single query into hundreds/thousands of search variations.

        Strategy:
        1. Parse the query into intent, products, business types, location
        2. Get all product/service synonyms
        3. Get all business type variations
        4. Get location expansion (state + cities + districts)
        5. Generate cartesian product of all combinations
        6. Add industry verticals
        7. Add generic India-level searches
        8. Deduplicate, sort by priority, trim to max_queries
        """
        parsed = self._parse_query(query)
        variations = []

        # Detect query type for smart expansion
        query_type = self._detect_query_type(query)

        # Get expansion terms
        product_terms = self._get_product_terms(parsed["products"])
        business_terms = self._get_business_terms(parsed["business_types"])
        locations = self._get_locations(parsed["location"])

        # Strategy A: If we have products + business types + locations → full cross-product
        if product_terms and business_terms and locations:
            cross_product_vars = self._generate_cross_product(
                product_terms, business_terms, locations, parsed
            )
            variations.extend(cross_product_vars)

        # Strategy B: For service/industry queries (e.g., "Restaurants Hyderabad")
        if query_type in ("service_search", "industry_search") or not product_terms:
            service_vars = self._generate_service_variations(
                query, parsed, locations
            )
            variations.extend(service_vars)

        # Strategy C: Industry vertical variations
        relevant_industries = self._relevant_industries(parsed["products"], query)
        if relevant_industries:
            industry_vars = self._generate_industry_variations(
                relevant_industries, locations
            )
            variations.extend(industry_vars)

        # Strategy D: Generic search terms for every location
        generic_vars = self._generate_generic_variations(
            product_terms or [parsed["raw"]], locations
        )
        variations.extend(generic_vars)

        # Deduplicate
        unique = self._deduplicate(variations)

        # Sort by priority
        unique.sort(key=lambda x: (-x["priority"], x["query"]))

        logger.info(
            f"Expanded '{query}' (type={query_type}) into {len(unique)} search variations "
            f"(products={len(product_terms)}, biz={len(business_terms)}, locs={len(locations)})"
        )
        return unique[:max_queries]

    def _detect_query_type(self, query: str) -> str:
        """Detect the type of search query."""
        q = query.lower().strip()

        for qtype, pattern in QUERY_TYPES.items():
            if re.search(pattern, q, re.IGNORECASE):
                return qtype

        # Check if any known product is mentioned
        for product in sorted(PRODUCT_SYNONYMS.keys(), key=len, reverse=True):
            if product in q:
                return "product_buyer"

        # Check if any industry is mentioned
        for industry in INDUSTRY_VERTICALS:
            if industry.split()[0] in q:
                return "industry_search"

        # Default: treat as general search
        return "general"

    def _parse_query(self, query: str) -> dict:
        """Parse user query into structured components.

        Handles:
        - "Palm Oil Buyers India" → product=palm oil, type=buyer, location=India
        - "Restaurants Hyderabad" → product=restaurant, type=services, location=Hyderabad
        - "Soap Manufacturers" → product=soap, type=manufacturer
        - "Food Manufacturers Karnataka" → product=food, type=manufacturer, location=Karnataka
        """
        query_lower = query.lower().strip()

        # Extract products (check multi-word first, then single)
        products = []
        for keyword in sorted(PRODUCT_SYNONYMS.keys(), key=len, reverse=True):
            if keyword in query_lower:
                products.append(keyword)
                # Remove from query string to avoid double matching
                # but don't modify query_lower for other extractions
                break  # Take the best match only

        if not products:
            # Check against all known words
            for product in sorted(PRODUCT_SYNONYMS.keys(), key=len, reverse=True):
                words = product.split()
                if len(words) <= 2 and all(w in query_lower.split() for w in words):
                    products.append(product)
                    break

        if not products:
            # Check single words
            for word in query_lower.split():
                for product in PRODUCT_SYNONYMS:
                    if word == product or word in PRODUCT_SYNONYMS[product]:
                        products.append(product)
                        break
                if products:
                    break

        if not products:
            # Take first meaningful word
            stop_words = {"the", "of", "in", "for", "and", "or", "to", "a", "an",
                          "is", "are", "buy", "get", "find", "search", "list",
                          "top", "best", "all", "india", "companies", "company"}
            words = [w for w in query_lower.split() if w not in stop_words]
            if words:
                products = [words[0]]

        # Extract business types
        business_types = []
        for btype, aliases in BUSINESS_TYPES.items():
            if btype in query_lower:
                business_types.append(btype)
            else:
                for alias in aliases:
                    if alias in query_lower:
                        business_types.append(btype)
                        break

        if not business_types:
            # Infer from query type
            query_type = self._detect_query_type(query)
            if query_type == "service_search":
                # Services like restaurants, hotels - just product name + location
                business_types = [""]  # Empty = just "restaurant Hyderabad"
            elif query_type == "industry_search":
                business_types = ["manufacturers", "suppliers", "processors"]
            elif query_type == "import_export":
                business_types = ["importers", "exporters", "traders"]
            else:
                business_types = ["buyers", "manufacturers", "suppliers", "traders"]

        # Extract location
        location = self._extract_location(query_lower)

        return {
            "products": products,
            "business_types": business_types,
            "location": location,
            "raw": query,
        }

    def _extract_location(self, query_lower: str) -> str | None:
        """Extract location from query. Returns state name if possible."""
        # Check for state names directly
        for state in ALL_STATES:
            if state.lower() in query_lower:
                return state

        # Check for city names → return parent state
        for state, cities in INDIAN_STATES_CITIES.items():
            for city in cities:
                if city.lower() in query_lower:
                    return state

        # Check for common tokens
        if "india" in query_lower:
            return None  # India-wide search

        return None

    def _get_product_terms(self, products: list[str]) -> list[str]:
        """Get all product search terms including synonyms."""
        if not products:
            return []
        terms = []
        for product in products:
            if product in PRODUCT_SYNONYMS:
                terms.extend(PRODUCT_SYNONYMS[product])
            else:
                terms.append(product)
        return list(dict.fromkeys(terms))[:30]  # Max 30 synonyms per product

    def _get_business_terms(self, business_types: list[str]) -> list[str]:
        """Get all business type search terms."""
        if not business_types:
            return ["buyer", "manufacturer", "supplier", "trader"]
        terms = []
        for btype in business_types:
            if btype in BUSINESS_TYPES:
                terms.extend(BUSINESS_TYPES[btype])
            else:
                terms.append(btype)
        return list(dict.fromkeys(terms))

    def _get_locations(self, location: str | None) -> list[str]:
        """Get all location search terms.

        If location is None (India-wide), expand to ALL states and top cities.
        If location is a state, include state + all its cities.
        """
        if not location:
            locs = ["India"]
            # Add all states
            locs.extend(ALL_STATES)
            # Add top 5 cities from top 10 states
            top_states = ["Maharashtra", "Gujarat", "Karnataka", "Tamil Nadu",
                          "Uttar Pradesh", "West Bengal", "Rajasthan", "Telangana",
                          "Kerala", "Delhi"]
            for state in top_states:
                cities = INDIAN_STATES_CITIES.get(state, [])
                locs.extend(cities[:5])
            return list(dict.fromkeys(locs))

        # Specific location - state + its cities
        locs = [location]
        cities = INDIAN_STATES_CITIES.get(location, [])
        locs.extend(cities)
        return list(dict.fromkeys(locs))

    def _generate_cross_product(
        self, product_terms: list[str], business_terms: list[str],
        locations: list[str], parsed: dict
    ) -> list[dict]:
        """Generate cross-product of products × business types × locations."""
        variations = []

        for product in product_terms[:10]:  # Limit products to keep manageable
            for biz in business_terms:
                for location in locations:
                    if biz:
                        query_str = f"{product} {biz}"
                    else:
                        query_str = product
                    if location and location != "India":
                        query_str += f" {location}"

                    source = self._best_source(query_str)
                    priority = SOURCE_DEFINITIONS.get(source, {}).get("priority", 5)

                    variations.append({
                        "query": query_str,
                        "source": source,
                        "intent": f"{biz or 'find'} {product} in {location or 'India'}",
                        "location": location,
                        "priority": priority,
                        "query_type": "cross_product",
                    })

        return variations

    def _generate_service_variations(
        self, query: str, parsed: dict, locations: list[str]
    ) -> list[dict]:
        """Generate variations for service/industry queries like 'Restaurants Hyderabad'."""
        variations = []
        q = query.lower().strip()

        # Get the main service word(s)
        service_words = []
        for word in q.split():
            if word not in ("in", "at", "the", "of", "for", "and", "near", "top", "best"):
                service_words.append(word)

        # Remove location words
        location = parsed.get("location")
        location_lower = location.lower() if location else ""
        if location and location_lower:
            for city in INDIAN_STATES_CITIES.get(location, []):
                if city.lower() in q:
                    service_words = [w for w in service_words if w.lower() not in city.lower().split()]
            if location_lower in " ".join(service_words).lower():
                service_words = [w for w in service_words if w.lower() != location_lower]

        service_term = " ".join(service_words) if service_words else q

        # Get synonyms for the service
        service_synonyms = [service_term]
        for product, synonyms in PRODUCT_SYNONYMS.items():
            if product in service_term.lower() or service_term.lower() in product:
                service_synonyms = synonyms[:5]
                break

        # Generate for each location
        for service in service_synonyms:
            for location in locations[:15]:  # Limit locations
                query_str = f"{service}"
                if location and location != "India":
                    query_str += f" {location}"

                source = self._best_source(query_str)
                variations.append({
                    "query": query_str,
                    "source": source,
                    "intent": f"Find {service} in {location or 'India'}",
                    "location": location,
                    "priority": SOURCE_DEFINITIONS.get(source, {}).get("priority", 7) - 1,
                    "query_type": "service_search",
                })

        return variations

    def _generate_industry_variations(
        self, industries: list[str], locations: list[str]
    ) -> list[dict]:
        """Generate industry-based search variations."""
        variations = []

        for industry in industries:
            for location in locations[:10]:  # Top 10 locations for industries
                query_str = f"{industry}"
                if location and location != "India":
                    query_str += f" {location}"

                source = self._best_source(query_str)
                variations.append({
                    "query": query_str,
                    "source": source,
                    "intent": f"Find {industry} in {location or 'India'}",
                    "location": location,
                    "priority": SOURCE_DEFINITIONS.get(source, {}).get("priority", 6) - 1,
                    "query_type": "industry_search",
                })

        return variations

    def _generate_generic_variations(
        self, product_terms: list[str], locations: list[str]
    ) -> list[dict]:
        """Generate generic search variations like 'palm oil buyers India'."""
        variations = []
        suffixes = ["buyers", "importers", "suppliers", "distributors",
                     "wholesalers", "manufacturers", "traders", "dealers"]

        products = product_terms[:5] if product_terms else [""]

        for product in products:
            for suffix in suffixes:
                for location in locations[:8]:  # Top locations for generic
                    query_str = f"{product} {suffix}"
                    if location and location != "India":
                        query_str += f" {location}"
                    elif location:
                        query_str += " India"

                    variations.append({
                        "query": query_str.strip(),
                        "source": "indiamart",
                        "intent": f"Find {suffix} of {product} in {location or 'India'}",
                        "location": location,
                        "priority": 8,
                        "query_type": "generic",
                    })

        return variations

    def _relevant_industries(self, products: list[str], query: str) -> list[str]:
        """Get industry verticals relevant to the query."""
        relevant = set()
        text = " ".join(products).lower() + " " + query.lower()

        # Oil-related
        oil_keywords = ["palm oil", "sunflower oil", "soybean oil", "mustard oil",
                        "vegetable oil", "edible oil", "cooking oil", "vanaspati",
                        "shortening", "bakery fat", "refined oil", "groundnut oil",
                        "coconut oil", "rice bran oil", "frying oil", "margarine"]
        if any(k in text for k in oil_keywords):
            relevant.update([
                "food manufacturer", "snack manufacturer", "bakery", "bakery manufacturer",
                "biscuit manufacturer", "confectionery manufacturer", "chocolate factory",
                "ice cream manufacturer", "namkeen manufacturer",
                "soap manufacturer", "detergent manufacturer", "vanaspati manufacturer",
                "shortening manufacturer", "edible oil manufacturer", "oil refinery",
                "restaurant", "hotel", "animal feed manufacturer",
                "FMCG company", "oleochemical manufacturer",
            ])

        # Soap/detergent related
        soap_keywords = ["soap", "detergent", "hand wash", "cleaning"]
        if any(k in text for k in soap_keywords):
            relevant.update([
                "soap manufacturer", "detergent manufacturer", "cleaning products company",
                "personal care company", "FMCG company", "cosmetic manufacturer",
            ])

        # Food related
        food_keywords = ["food", "bakery", "biscuit", "snack", "namkeen", "chocolate",
                         "confectionery", "ice cream", "noodle", "dairy", "ghee",
                         "spice", "tea", "coffee", "sugar", "rice", "flour"]
        if any(k in text for k in food_keywords):
            relevant.update([
                "food manufacturer", "snack manufacturer", "bakery", "bakery manufacturer",
                "biscuit manufacturer", "confectionery manufacturer", "chocolate factory",
                "ice cream manufacturer", "namkeen manufacturer", "noodle manufacturer",
                "packaged food company", "food processing company",
            ])

        # Feed related
        feed_keywords = ["animal feed", "poultry feed", "feed"]
        if any(k in text for k in feed_keywords):
            relevant.update([
                "animal feed manufacturer", "feed mill", "poultry feed manufacturer",
                "poultry farm", "dairy farm",
            ])

        # Restaurant/Hotel related
        service_keywords = ["restaurant", "hotel", "cafe", "cloud kitchen", "catering"]
        if any(k in text for k in service_keywords):
            relevant.update([
                "restaurant", "restaurant chain", "hotel", "hotel chain",
                "cloud kitchen", "catering company", "food service",
            ])

        # If nothing matched, add common ones
        if not relevant:
            relevant.add("food manufacturer")
            relevant.add("FMCG company")

        return list(relevant)

    def _deduplicate(self, variations: list[dict]) -> list[dict]:
        """Remove duplicate queries across sources."""
        seen = set()
        unique = []
        for v in variations:
            key = (v["query"].lower().strip(), v["source"])
            if key not in seen:
                seen.add(key)
                unique.append(v)
        return unique

    def _best_source(self, query: str) -> str:
        """Recommend the best source for a given query."""
        q = query.lower()

        # Import/export queries -> exportersindia"
        if any(w in q for w in ["import", "export", "trading", "exporter", "importer",
                                 "international", "overseas"]):
            return "exportersindia"

        # Service/business queries -> justdial
        if any(w in q for w in ["distributor", "wholesal", "dealer", "retail",
                                 "store", "supermarket", "services", "near me"]):
            return "justdial"

        # Restaurant/hotel/cafe -> justdial (local directories are best)
        if any(w in q for w in ["restaurant", "hotel", "cafe", "dining",
                                 "catering", "cloud kitchen"]):
            return "justdial"

        # Manufacturer/industry queries -> tradeindia
        if any(w in q for w in ["manufactur", "factory", "refin", "processing",
                                 "industry", "mill", "plant"]):
            return "tradeindia"

        # Default: prefer tradeindia or justdial over indiamart (which has been unreliable)
        return "tradeindia"

    def get_source_summary(self, variations: list[dict]) -> dict:
        """Get a summary of variations grouped by source."""
        summary = {}
        for v in variations:
            src = v["source"]
            if src not in summary:
                summary[src] = 0
            summary[src] += 1
        return summary
