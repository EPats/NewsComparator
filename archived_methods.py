import re
import nltk
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.corpus import wordnet, stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from gensim import corpora
from gensim.models.ldamodel import LdaModel
import numpy as np
import spacy
from sklearn.feature_extraction.text import TfidfVectorizer
from collections import defaultdict, Counter
import json


nltk.download('stopwords')


def get_wordnet_pos(treebank_tag):
    """
    Map POS tag to first character used by WordNetLemmatizer
    """
    tag = {
        'J': wordnet.ADJ,
        'N': wordnet.NOUN,
        'V': wordnet.VERB,
        'R': wordnet.ADV
    }
    return tag.get(treebank_tag[0], wordnet.NOUN)


def lemmatize_text(text, stop_words):
    text = text.lower()
    text = re.sub(r'[^\s]*@[^\s]', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    lemmatizer = WordNetLemmatizer()
    tokenized_sent = sent_tokenize(text)

    lemmatized_sent = []
    for sentence in tokenized_sent:
        tokenized_words = word_tokenize(sentence)
        word_pos = nltk.pos_tag(tokenized_words)
        lemmatized_words = [lemmatizer.lemmatize(word, get_wordnet_pos(pos)) for word, pos in word_pos if word not in stop_words and word not in ["'s", "'re"]]
        lemmatized_sent.append(' '.join(lemmatized_words))

    return lemmatized_sent


def preprocess(text, stop_words):
    tokens = re.findall(r'\b\w+\b', text.lower())
    tokens = [t for t in tokens if t not in stop_words]
    return tokens


def extract_ngrams(text, n):
    words = word_tokenize(text)
    words = [word for word in words if re.search(r'\w', word)]
    # Extracting n-grams from the list of words
    ngrams = [tuple(words[i:i + n]) for i in range(len(words) - n + 1)]

    return [' '.join(ngram) for ngram in ngrams]


def rake_keywords(text, stopwords):
    # Define stopwords, punctuations and split by sentence
    punctuations = '[!\"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~]'
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s', text)

    # Generate phrases for each sentence
    phrases = []
    for sentence in sentences:
        words = [word.lower() for word in re.split(punctuations, sentence) if word]
        phrase = []
        for word in words:
            if word in stopwords:
                if phrase:
                    phrases.append(phrase)
                    phrase = []
            else:
                phrase.append(word)
        if phrase:
            phrases.append(phrase)

    # Score words using RAKE methodology
    word_freq = Counter()
    word_degree = Counter()
    for phrase in phrases:
        unique_words = set(phrase)
        for word in unique_words:
            word_freq[word] += 1
            word_degree[word] += len(phrase)

    scores = {word: word_degree[word] / word_freq[word] for word in word_freq}

    # Extract keywords
    sorted_keywords = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return sorted_keywords

def analyse_from_file(path: str):

    articles = []
    with open(path, 'r') as file:
        articles = json.load(file)

    nlp = spacy.load("en_core_web_sm")

    stop_words = set(stopwords.words('english'))
    for article in articles:

    #### need to fix pulls, subtitles are sometimes lists, sometimes sttrings
        sub = article['subtitle'] if type(article['subtitle']) == list else [article['subtitle']] if article['subtitle'] else []
        article['full_text'] = ' '.join(([article['title']] if article['title'] else [])
                                        + sub + [text for text in article['article_text'] if re.sub(r'[^\w\s]', '', text)])
        lemmatized_sentences = lemmatize_text(article['full_text'], stop_words)
        article['lemmatized_text'] = ' '.join(lemmatized_sentences)


    corpus_raw_text = [article['full_text'] for article in articles]
    corpus_lem_text = [article['lemmatized_text'] for article in articles]
    # Initialize and fit TF-IDF vectorizer
    vectorizer_raw = TfidfVectorizer()
    vectorizer_lem = TfidfVectorizer()
    tfidf_matrix_raw = vectorizer_raw.fit_transform(corpus_raw_text)
    tfidf_matrix_lem = vectorizer_lem.fit_transform(corpus_lem_text)

    # To get top N keywords for a document based on tf-idf score:
    N = 5
    for i, article in enumerate(articles):
        feature_array_raw = np.array(vectorizer_raw.get_feature_names_out())
        tfidf_sorting_raw = np.argsort(tfidf_matrix_raw[i].toarray()).flatten()[::-1]
        top_keywords_raw = []
        j = 0
        for keyword in feature_array_raw[tfidf_sorting_raw]:
            if keyword not in stop_words:
                top_keywords_raw.append(keyword)
                j += 1
            if j >= N:
                break
        feature_array_lem = np.array(vectorizer_lem.get_feature_names_out())
        tfidf_sorting_lem = np.argsort(tfidf_matrix_lem[i].toarray()).flatten()[::-1]
        top_keywords_lem = [keyword for keyword in feature_array_lem[tfidf_sorting_lem][:N]]
        print(f'Document: {article["url"]}\nTop {N} keywords: {top_keywords_raw}\nTop {N} lem keywords: {top_keywords_lem}\n')
        article['raw_keywords'] = top_keywords_raw
        article['lem_keywords'] = top_keywords_lem

        texts = [preprocess(sent, stop_words) for sent in article['full_text'].split('.')]
        dictionary = corpora.Dictionary(texts)
        corpus = [dictionary.doc2bow(text) for text in texts]
        lda_model = LdaModel(corpus, num_topics=3, id2word=dictionary, random_state=42)
        topics = lda_model.print_topics(num_words=5)
        print(f'Topics: {topics}')
        article['raw_lda_topics'] = topics

        texts = [preprocess(sent, stop_words) for sent in article['lemmatized_text'].split('.')]
        dictionary = corpora.Dictionary(texts)
        corpus = [dictionary.doc2bow(text) for text in texts]
        lda_model = LdaModel(corpus, num_topics=3, id2word=dictionary, random_state=42)
        topics = lda_model.print_topics(num_words=5)
        print(f'Lem Topics: {topics}')
        article['lem_lda_topics'] = topics

        bigrams = extract_ngrams(article['full_text'], 2)
        trigrams = extract_ngrams(article['full_text'], 3)
        bigram_freq = defaultdict(int)
        trigram_freq = defaultdict(int)
        for bigram in bigrams:
            bigram_freq[bigram] += 1

        for trigram in trigrams:
            trigram_freq[trigram] += 1

        top_bigrams = sorted(bigram_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        top_trigrams = sorted(trigram_freq.items(), key=lambda x: x[1], reverse=True)[:5]

        article['raw_bigrams'] = top_bigrams
        article['raw_trigrams'] = top_trigrams

        print(f'Raw bigrams: {top_bigrams}\nRaw trigrams{top_trigrams}')

        bigrams = extract_ngrams(article['lemmatized_text'], 2)
        trigrams = extract_ngrams(article['lemmatized_text'], 3)
        bigram_freq = defaultdict(int)
        trigram_freq = defaultdict(int)
        for bigram in bigrams:
            bigram_freq[bigram] += 1

        for trigram in trigrams:
            trigram_freq[trigram] += 1

        top_bigrams = sorted(bigram_freq.items(), key=lambda x: x[1], reverse=True)[:5]
        top_trigrams = sorted(trigram_freq.items(), key=lambda x: x[1], reverse=True)[:5]

        article['lem_bigrams'] = top_bigrams
        article['lem_trigrams'] = top_trigrams

        print(f'Lem bigrams: {top_bigrams}\nLem trigrams{top_trigrams}')

        raked_keywords = rake_keywords(article['lemmatized_text'], stop_words)
        article['rake_keywords'] = raked_keywords
        print(f'Rake keywords: {raked_keywords}')

        doc = nlp(article['full_text'])
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        article['entities'] = entities
        print(f'Entities: {entities}')

    # Saving the scraped articles to a JSON file.
    with open('data3.json', 'w') as outfile:
        outfile.write(json.dumps(articles, indent=4))