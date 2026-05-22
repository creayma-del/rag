import click
import os
from src.document_loader import DocumentLoader
from src.vector_store import VectorStoreManager
from src.qa_engine import QAEngine
from config import Config

@click.group()
def cli():
    pass

@cli.command()
@click.option('--path', default=Config.DOCUMENTS_PATH, help='文档目录路径')
def build(path):
    doc_loader = DocumentLoader()
    vector_store_manager = VectorStoreManager()
    
    print(f"从 {path} 加载文档...")
    documents = doc_loader.load_documents(path)
    
    if not documents:
        print("未找到任何文档")
        return
    
    print(f"加载了 {len(documents)} 个文档")
    
    split_docs = doc_loader.split_documents(documents)
    print(f"分割成 {len(split_docs)} 个文档块")
    
    vector_store_manager.create_vector_store(split_docs)
    print("向量数据库构建完成")

@cli.command()
@click.option('--query', prompt='请输入查询问题', help='要查询的问题')
@click.option('--model', default=Config.DEFAULT_MODEL, 
              type=click.Choice(['openai', 'qwen', 'zhipu', 'kimi', 'doubao', 'local', 'local-small', 'local-medium', 'local-large', 'local-huge']),
              help='选择大模型')
def query(query, model):
    vector_store_manager = VectorStoreManager()
    vector_store = vector_store_manager.load_vector_store()
    
    if vector_store is None:
        print("向量数据库不存在，请先运行 build 命令")
        return
    
    try:
        qa_engine = QAEngine(vector_store, model_name=model)
        print(f"使用模型: {model}")
        answer = qa_engine.get_answer(query)
        print(f"\n答案：{answer}")
    except ValueError as e:
        print(f"错误：{e}")

@cli.command()
@click.option('--model', default=Config.DEFAULT_MODEL, 
              type=click.Choice(['openai', 'qwen', 'zhipu', 'kimi', 'doubao', 'local', 'local-small', 'local-medium', 'local-large', 'local-huge']),
              help='选择大模型')
def chat(model):
    vector_store_manager = VectorStoreManager()
    vector_store = vector_store_manager.load_vector_store()
    
    if vector_store is None:
        print("向量数据库不存在，请先运行 build 命令")
        return
    
    try:
        qa_engine = QAEngine(vector_store, model_name=model)
        print(f"\n知识库已就绪！使用模型: {model}")
        print("输入问题进行查询，输入 'exit' 退出")
        
        while True:
            question = input("\n请输入您的问题：")
            
            if question.lower() == "exit":
                print("退出程序")
                break
            
            if not question.strip():
                continue
            
            try:
                answer = qa_engine.get_answer(question)
                print(f"\n答案：{answer}")
            except Exception as e:
                print(f"发生错误：{e}")
    except ValueError as e:
        print(f"错误：{e}")

@cli.command()
def models():
    print("支持的模型列表:")
    print("\n--- 云端模型（需要API Key）---")
    for model_name, config in Config.MODEL_CONFIGS.items():
        if not model_name.startswith("local"):
            desc = config.get('description', config.get('model', ''))
            print(f"  - {model_name}: {desc}")
    
    print("\n--- 本地模型（无需API Key）---")
    for model_name, config in Config.MODEL_CONFIGS.items():
        if model_name.startswith("local"):
            desc = config.get('description', config.get('model', ''))
            print(f"  - {model_name}: {desc}")
    
    print("\n使用方式:")
    print("  python3 cli.py query --model qwen --query '你的问题'")
    print("  python3 cli.py chat --model local-large")

if __name__ == '__main__':
    cli()
