from src.rag.retriever import CocciRetriever
import inspect

print("Checking CocciRetriever...")
r = CocciRetriever
methods = [m[0] for m in inspect.getmembers(r, predicate=inspect.isfunction)]
print(f"Methods: {methods}")

if 'ingest_knowledge' in methods and 'retrieve_structured' in methods:
    print("Verification Success: Methods found.")
else:
    print("Verification Failed: Missing methods.")
