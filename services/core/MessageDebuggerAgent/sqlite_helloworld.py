from sqlalchemy import create_engine
from sqlalchemy import Column, String, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

ORMBase = declarative_base()


def sqlite_helloworld():
    path = '$VOLTTRON_HOME/data/test_db.sqlite'
    engine = create_engine('sqlite:///' + path).connect()
    ORMBase.metadata.create_all(engine)
    db_session = sessionmaker(bind=engine)()


class DebugMessage(ORMBase):

    __tablename__ = 'TestTable'

    rowid = Column(Integer, primary_key=True)
    another_field = Column(String)
