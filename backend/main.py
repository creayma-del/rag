import os
import sys
from src.document_loader import DocumentLoader
from src.vector_store import VectorStoreManager
from src.qa_engine import QAEngine
from config import Config

def initialize_knowledge_base():
    print("初始化知识库...")
    
    doc_loader = DocumentLoader()
    vector_store_manager = VectorStoreManager()
    
    if os.path.exists(Config.VECTOR_DB_PATH) and len(os.listdir(Config.VECTOR_DB_PATH)) > 0:
        print("加载已存在的向量数据库...")
        vector_store = vector_store_manager.load_vector_store()
    else:
        print("创建新的向量数据库...")
        documents = doc_loader.load_documents(Config.DOCUMENTS_PATH)
        
        if not documents:
            print("未找到任何文档，跳过创建向量数据库")
            return None
        
        print(f"加载了 {len(documents)} 个文档")
        
        split_docs = doc_loader.split_documents(documents)
        print(f"分割成 {len(split_docs)} 个文档块")
        
        vector_store = vector_store_manager.create_vector_store(split_docs)
        print("向量数据库创建完成")
    
    return vector_store

def main():
    vector_store = initialize_knowledge_base()
    
    if vector_store is None:
        print("无法初始化知识库，请确保 documents 目录中有文档")
        return
    
    qa_engine = QAEngine(vector_store)
    print("\n知识库已就绪！输入问题进行查询，输入 'exit' 退出")
    
    while True:
        question = input("\n请输入您的问题：")
        
        if question.lower() == "exit":
            print("退出程序")
            break
        
        if not question.strip():
            continue
        
        try:
            result = qa_engine.get_answer(question)
            answer = result["answer"] if isinstance(result, dict) else str(result)
            print(f"\n答案：{answer}")
        except Exception as e:
            print(f"发生错误：{e}")

if __name__ == "__main__":
    main()