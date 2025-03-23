from setuptools import setup, find_packages

setup(
    name="graph_space_v2",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        # Core dependencies
        "torch>=1.8.0",
        "torch-geometric>=2.0.0",
        "networkx>=2.5",
        "numpy>=1.19.0",
        "scikit-learn>=0.24.0",
        "node2vec>=0.3.0",

        # NLP and machine learning
        "transformers>=4.5.0",
        "sentence-transformers>=2.2.2",
        "faiss-cpu>=1.7.0",
        "langchain>=0.1.0",
        "langchain-text-splitters>=0.0.1",

        # LLM providers
        "openai>=1.0.0",

        # Web framework
        "flask>=2.0.0",
        "flask-cors>=3.0.10",
        "flask-jwt-extended>=4.4.0",

        # Document processing
        "PyPDF2>=3.0.0",
        "python-docx>=0.8.11",
        "pdfminer.six>=20220524",
        "markdown>=3.0.1",
        "bs4>=0.0.1",
        "filetype>=1.2.0",
        "openpyxl>=3.1.0",

        # Google integration
        "google-api-python-client>=2.100.0",
        "google-auth-httplib2>=0.1.0",
        "google-auth-oauthlib>=1.0.0",

        # Calendar integration
        "icalendar>=4.0.0",
        "recurring_ical_events>=1.0.0",

        # Utilities
        "tqdm>=4.65.0",
        "requests>=2.28.0",
        "matplotlib>=3.3.0",
        "python-dotenv>=1.0.0",
        "pyjwt>=2.4.0",
    ],
    entry_points={
        'console_scripts': [
            'graphspace=graph_space_v2.run:main',
        ],
    },
    python_requires=">=3.8",
    author="GraphSpace Development Team",
    author_email="info@graphspace.example.com",
    description="A modular knowledge graph-based productivity assistant",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    keywords="knowledge graph, productivity, RAG, GNN, ai assistant",
    url="https://github.com/example/graph_space",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Topic :: Office/Business :: Scheduling",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
)
