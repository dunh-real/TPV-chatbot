import uuid
from datetime import datetime

class GenerateID:
    def __init__(self):
        self.auto_generated_id = uuid.uuid4()
    
    def generate_id(self):
        string_id = str(self.auto_generated_id) + str(datetime.now())
        return string_id