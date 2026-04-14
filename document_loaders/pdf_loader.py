from langchain_community.document_loaders import PyPDFLoader

class PDFLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.loader = PyPDFLoader(file_path)
        
    def load(self):
        return self.loader.load()
    
    
    