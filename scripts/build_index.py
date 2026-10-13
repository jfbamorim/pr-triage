from openai import OpenAI

from pr_triage.rag.index import build_index

if __name__ == "__main__":
    print(f"{build_index(OpenAI())} chunks indexados")