argument = (
  'DC',
  {'intents': [{'device': 'light', 'action': 'on'}, {'device': 'fan', 'action': 'on'}]},
  {'DC': 0.95, 'KB': 0.4301, 'MACRO': 0.1, 'GPT': 0.2}
)

def anythingthis(decision,
    payload,
    scores):
    print(decision)
    print(payload["intents"])
    print(scores)
anythingthis(*argument)