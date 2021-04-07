from volttron.platform.vip.agent import Agent
from volttrontesting.utils.utils import  AgentMock
from vcplatform.agent import VolttronCentralPlatform


# Patch the VolttronCentralPlatform so the underlying Agent interfaces are mocked
# so we can just test the things that the PlatformWebService is responsible for.
VolttronCentralPlatform.__bases__ = (AgentMock.imitate(Agent, Agent()),)


