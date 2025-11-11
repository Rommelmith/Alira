from kb_operation import load_kb, load_or_build_index, query_kb
items = load_kb()
load_or_build_index(items, cache_path="kbtfid.pkl")
print(query_kb("what is my main laptop?"))
