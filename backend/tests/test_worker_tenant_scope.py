from uuid import uuid4

from app.workers.handlers import _get_organization_record


class Column:
    def __init__(self, name):
        self.name = name

    def __eq__(self, value):
        return self.name, value


class Record:
    id = Column("id")
    organization_id = Column("organization_id")


class Query:
    def __init__(self):
        self.conditions = ()

    def filter(self, *conditions):
        self.conditions = conditions
        return self

    def first(self):
        return None


class Database:
    def __init__(self):
        self.model = None
        self.query_object = Query()

    def query(self, model):
        self.model = model
        return self.query_object


def test_worker_record_lookup_always_includes_organization_scope():
    db = Database()
    record_id = uuid4()
    organization_id = uuid4()

    assert _get_organization_record(db, Record, record_id, organization_id) is None
    assert db.model is Record
    assert db.query_object.conditions == (
        ("id", record_id),
        ("organization_id", organization_id),
    )
