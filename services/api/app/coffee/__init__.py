"""Coffee keyword discovery — a self-contained add-on.

Everything this feature needs lives in this package: the market vocabulary, the
scan, the scoring, the response models and the routes. It reads from the rest
of the app (`collectors.serpapi_client`, `collectors.normalize.domain_of`,
`auth`, `db`, `models`) but changes nothing in it, so it can be added or
dropped by editing one line of `main.py`.
"""
