from sakubot.plugin import Plugin
from .pdf import Extension as PDF
from .documents import Extension as Documents
from .spreadsheets import Extension as Spreadsheets


class Extension(Plugin):
    name = 'office'

    def setup(self):
        self.providers = []
        for provider_class in (PDF, Documents, Spreadsheets):
            provider = provider_class(self.runtime)
            provider.id = self.id
            provider.setup()
            self.providers.append(provider)
