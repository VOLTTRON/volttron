"""
    This is a little test jig to confirm the ability to create a SQLite database
    and connect a SQL Alchemy session to it, building a test table in the process.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy import Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

ORMBase = declarative_base()


def sqlite_helloworld():
    path = os.path.expandvars('$VOLTTRON_HOME/data/test_db.sqlite')
    engine = create_engine('sqlite:///' + path).connect()
    ORMBase.metadata.create_all(engine)
    db_session = sessionmaker(bind=engine)()
    print('db_session = {}'.format(db_session))


class TestTable(ORMBase):

    __tablename__ = 'TestTable'

    rowid = Column(Integer, primary_key=True)
    another_field = Column(String)


if __name__ == '__main__':
    sqlite_helloworld()
