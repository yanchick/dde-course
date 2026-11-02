---
title: Литература
description: Книги и статьи к лекциям курса «Инжиниринг данных».
---

# Литература

Подборка книг и статей к лекциям курса. Источники сгруппированы по темам продвинутого уровня — от архитектуры данных до LLM и агентных систем.

## Архитектура систем обработки данных

### Введение в данные и их значение
- **"Big Data: A Revolution That Will Transform How We Live, Work, and Think"** — Kenneth Cukier, Viktor Mayer-Schönberger (2013). Классический труд о значении больших данных для общества и бизнеса.
- **"The Data Warehouse Toolkit: The Definitive Guide to Dimensional Modeling"** — Ralph Kimball, Margy Ross (3-е издание, 2013). Фундаментальная книга о проектировании хранилищ данных.
- **"Fundamentals of Data Engineering"** — Joe Reis, Matt Housley (2022). Современный учебник, охватывающий основные концепции инженерии данных.
- **"The Art of Statistics: Learning from Data"** — David Spiegelhalter (2019). Доступное введение в статистику и анализ данных.

### Основные концепции инженерии данных
- **"Designing Data-Intensive Applications"** — Martin Kleppmann (2017). Лучшая книга о проектировании масштабируемых систем обработки данных.
- **"Building Microservices: Designing Fine-Grained Systems"** — Sam Newman (2-е издание, 2021). Подробное руководство по микросервисной архитектуре.
- **"The Phoenix Project: A Novel About IT, DevOps, and Helping Your Business Win"** — Gene Kim, Kevin Behr, George Spafford (2018). Практический взгляд на DevOps и системное мышление.
- **"Data Pipelines Pocket Reference"** — James Densmore (2021). Компактный справочник по построению пайплайнов данных.

### Архитектуры инжиниринга данных
- **"Lambda Architecture"** — Nathan Marz (статья на O'Reilly, 2015). Оригинальное описание лямбда-архитектуры.
- **"Kappa Architecture"** — Jay Kreps (статья в блоге LinkedIn, 2014). Введение в упрощенный подход к потоковой обработке.
- **"Data Mesh: Delivering Data-Driven Value at Scale"** — Zhamak Dehghani (статья на ThoughtWorks, 2020). Концепция децентрализованной архитектуры данных.
- **"The Data Lakehouse: Data Warehouses, Lakes, and Lakehouses"** — Matei Zaharia et al. (статья в CIDR, 2021). Гибридный подход к хранению данных.

### Микросервисы в инжиниринге данных
- **"Microservices Patterns"** — Chris Richardson (2018). Практические паттерны для микросервисной архитектуры[1][2].
- **"Microservices Architecture: Aligning Principles, Practices, and Culture"** — Irakli Nadareishvili, Matt McLarty, Michael Amundsen (2016). Комплексный подход к микросервисам.
- **"Release It!: Design and Deploy Production-Ready Software"** — Michael T. Nygard (2-е издание, 2018). О надежности распределенных систем.
- **"Streaming Systems: The What, Where, When, and How of Large-Scale Data Processing"** — Tyler Akidau, Slava Chernyak, Reuven Lax (2018). Теория потоковой обработки данных.

---

## Продвинутый сбор данных

### Работа с REST API и GraphQL
- **"RESTful Web Services"** — Leonard Richardson, Sam Ruby (2007). Классический учебник по REST архитектуре.
- **"Learning GraphQL"** — Alex Banks, Eve Porcello (2018). Полный курс по GraphQL для начинающих и опытных разработчиков.
- **"API Design Best Practices"** — Swagger/OpenAPI документация (постоянно обновляется). Современные стандарты проектирования API.
- **"The Art of API Design"** — статья на Medium и различные блоги (2020+). Практические советы по дизайну API.

### Web scraping с использованием Scrapy
- **"Learning Scrapy"** — Dimitrios Kouzis-Loukas (2016). Полное руководство по фреймворку Scrapy.
- **"Web Scraping with Python: Collecting More Data from the Modern Web"** — Ryan Mitchell (2-е издание, 2018). Практический учебник по веб-скрапингу.
- **"Scrapy Official Documentation"** — Scrapy Team (https://docs.scrapy.org/). Официальная документация с примерами.
- **"Automating Web Scraping with Selenium"** — статьи на Real Python и других платформах (2020+). Автоматизация динамических сайтов.

### Потоковая обработка данных
- **"Kafka: The Definitive Guide"** — Neha Narkhede, Gwen Shapira, Todd Palino (2-е издание, 2021). Полное руководство по Apache Kafka[1].
- **"Stream Processing with Apache Flink"** — Fabian Hueske, Vasiliki Kalavri (2019). Практическое введение в Apache Flink.
- **"Spark: The Definitive Guide"** — Bill Chambers, Matei Zaharia (2018). Comprehensive guide to Apache Spark, including Spark Streaming.
- **"Event Streaming with Kafka and Spring Boot"** — статьи на Spring.io и Baeldung (2021+). Практическое применение Kafka.

### Работа с большими файлами и распределенными системами
- **"Hadoop: The Definitive Guide"** — Tom White (4-е издание, 2015). Классический учебник по Hadoop и HDFS.
- **"Parquet File Format Specification"** — Apache Software Foundation (https://parquet.apache.org/). Официальная спецификация формата Parquet.
- **"Amazon S3 Best Practices"** — AWS Official Documentation (постоянно обновляется). Рекомендации по работе с S3.
- **"Distributed Systems: Principles and Paradigms"** — Andrew S. Tanenbaum, Maarten van Steen (2-е издание, 2006). Теоретические основы распределенных систем.

---

## Продвинутая очистка и валидация данных

### Автоматизация процессов очистки
- **"Data Cleaning 101"** — статьи на Towards Data Science (2020+). Практические техники очистки данных.
- **"Tidy Data"** — Hadley Wickham (статья в Journal of Statistical Software, 2014). Философия структурирования данных.
- **"Data Wrangling with Python"** — Jacqueline Kazil, Katharine Jarmul (2016). Практический учебник по очистке и трансформации данных.
- **"Pandas Documentation and Tutorials"** — Pandas Team (https://pandas.pydata.org/). Официальная документация с примерами.

### Статистические методы выявления аномалий
- **"Outlier Detection for Temporal Data"** — статьи на Towards Data Science и в академических журналах (2019+). Обнаружение аномалий во времени.
- **"Anomaly Detection: Algorithms, Explanations, and Applications"** — Markus M. Breunig, Hans-Peter Kriegel, Raymond T. Ng, Jörg Sander (статья в SIGMOD, 2000). Классический подход LOFAO.
- **"Isolation Forest"** — Fei Tony Liu, Kai Ming Ting, Zhi-Hua Zhou (статья в ICDM, 2008). Алгоритм изолирующего леса.
- **"Statistical Outlier Detection Using R"** — статьи на R-bloggers и в документации пакетов (2020+). Практическое применение статистических методов.

### Библиотеки для валидации данных
- **"Great Expectations Documentation"** — Great Expectations Team (https://docs.greatexpectations.io/). Официальная документация с примерами.
- **"Pandera: Statistical Data Validation of Pandas Dataframes"** — Niels Bantilan (https://pandera.readthedocs.io/). Документация и примеры использования.
- **"Pydantic Documentation"** — Pydantic Team (https://docs.pydantic.dev/). Валидация структурированных данных в Python.
- **"Data Quality Frameworks Comparison"** — статьи на Medium и блогах инженеров (2021+). Сравнение подходов к валидации.

### Профилирование данных
- **"Pandas Profiling Documentation"** — Pandas Profiling Team (https://pandas-profiling.ydata.ai/). Инструмент для автоматического профилирования.
- **"Sweetviz: In-depth EDA in just two lines of code"** — Sweetviz Documentation (https://pypi.org/project/sweetviz/). Быстрая визуализация данных.
- **"Data Profiling: State of the Art and Future Perspectives"** — статьи в академических журналах (2019+). Теория и практика профилирования.
- **"Data Quality Metrics and KPIs"** — статьи на Towards Data Science (2020+). Метрики оценки качества данных.

---

## Сложная предобработка и трансформация

### Feature engineering для машинного обучения
- **"Feature Engineering for Machine Learning"** — Alice Zheng, Amanda Casari (2018). Полное руководство по инжинирингу признаков.
- **"Automated Feature Engineering with Featuretools"** — Featuretools Documentation (https://featuretools.alteryx.com/). Автоматизация создания признаков.
- **"Imbalanced-learn: A Python Toolkit to Tackle the Curse of Imbalanced Datasets"** — Imbalanced-learn Team (https://imbalanced-learn.org/). Работа с несбалансированными данными.
- **"Scikit-learn: Machine Learning in Python"** — Scikit-learn Team (https://scikit-learn.org/). Инструменты для preprocessing и feature selection.

### Работа с временными рядами
- **"Time Series Analysis by State Space Methods"** — James Durbin, Siem Jan Koopman (2-е издание, 2012). Теоретические основы анализа временных рядов.
- **"Introduction to Time Series Forecasting with Python"** — Jason Brownlee (2021). Практический учебник по прогнозированию.
- **"tsfresh: Automatic Feature Extraction from Time Series"** — tsfresh Team (https://tsfresh.readthedocs.io/). Автоматическое создание признаков из временных рядов.
- **"Statsmodels Documentation"** — Statsmodels Team (https://www.statsmodels.org/). Статистические модели для временных рядов.

### Обработка текстовых данных (NLP)
- **"Natural Language Processing with Transformers"** — Lewis Tunstall, Leandro von Werra, Thomas Wolf (2022). Современный подход с трансформерами.
- **"Speech and Language Processing"** — Dan Jurafsky, James H. Martin (3-е издание, в процессе). Классический учебник по NLP.
- **"Hugging Face Transformers Documentation"** — Hugging Face Team (https://huggingface.co/docs/transformers/). Библиотека предобученных моделей.
- **"spaCy: Industrial-Strength Natural Language Processing"** — spaCy Team (https://spacy.io/). Практический фреймворк для NLP.

### Работа с изображениями и мультимедиа
- **"Deep Learning for Computer Vision"** — Adrian Rosebrock (2017). Практический учебник по обработке изображений.
- **"PyTorch Vision Documentation"** — PyTorch Team (https://pytorch.org/vision/). Инструменты для работы с изображениями.
- **"OpenCV Tutorials"** — OpenCV Team (https://docs.opencv.org/). Классическая библиотека компьютерного зрения.
- **"Audio Signal Processing with Python"** — статьи на Real Python и Towards Data Science (2020+). Обработка аудиоданных.

---

## Системы разметки и аннотации данных

### Платформы для разметки данных
- **"Label Studio Documentation"** — Label Studio Team (https://labelstudio.ai/). Открытая платформа для разметки.
- **"Prodigy: Radically efficient machine teaching"** — Explosion AI (https://prodi.gy/). Интерактивная разметка с активным обучением.
- **"Labelbox: The Data Foundation for AI"** — Labelbox Documentation (https://docs.labelbox.com/). Корпоративная платформа разметки.
- **"Amazon SageMaker Ground Truth"** — AWS Documentation (https://docs.aws.amazon.com/sagemaker/). Облачная платформа разметки.

### Активное обучение и semi-supervised learning
- **"Active Learning for Convolutional Neural Networks: A Core-Set Approach"** — Coreset Selection (2017). Теория активного обучения.
- **"Semi-Supervised Learning with Deep Generative Models"** — Durk P. Kingma, Danilo J. Mohamed (2014). Полу-контролируемое обучение.
- **"Snorkel: Rapid Training Data Creation with Weak Supervision"** — Alexander Ratner et al. (2017). Слабый надзор для разметки.
- **"Weak Supervision: The New Programming Paradigm for Machine Learning"** — статьи на Medium и блогах (2019+). Обзор слабого надзора.

### Контроль качества разметки
- **"Measuring Inter-Rater Reliability for Nominal Data: Why Setting Po is not Enough"** — Kilem L. Gwet (2014). Метрики согласия разметчиков.
- **"Crowdsourcing for Machine Learning"** — статьи на Towards Data Science (2020+). Управление толпой разметчиков.
- **"Data Annotation Best Practices"** — статьи на Medium и блогах компаний (2021+). Практические рекомендации.
- **"Quality Metrics for Data Labeling"** — статьи в блогах платформ разметки (2021+). Оценка качества разметки.

### Автоматизация процессов разметки
- **"Automated Data Labeling with Deep Learning"** — статьи на Towards Data Science (2020+). Автоматическая разметка моделями.
- **"Human-in-the-Loop Machine Learning"** — Robert Munro (2021). Взаимодействие человека и алгоритма.
- **"Data Programming: Creating Large Training Sets Quickly"** — Alexander Ratner et al. (2016). Программирование разметки.
- **"Programmatic Data Labeling"** — статьи на Medium и в документации Snorkel (2020+). Практическое применение.

---

## ETL/ELT пайплайны и оркестрация

### Apache Airflow для оркестрации
- **"The Airflow Book: A Complete Guide to Workflow Orchestration"** — Bas P. Harenslak, Julian de Ruiter (2021). Полное руководство по Airflow.
- **"Apache Airflow Official Documentation"** — Apache Airflow Team (https://airflow.apache.org/). Официальная документация.
- **"Orchestrating Data Pipelines with Apache Airflow"** — статьи на Real Python и Datacamp (2020+). Практические примеры.
- **"Workflow Orchestration with Apache Airflow"** — Udemy и другие курсы (2021+). Видеоуроки и интерактивные примеры.

### Дизайн надежных пайплайнов
- **"Building Reliable Data Pipelines"** — статьи на Towards Data Science (2020+). Принципы надежности.
- **"Idempotent Data Pipelines"** — статьи на блогах инженеров (2019+). Идемпотентность операций.
- **"Testing Data Pipelines"** — статьи на Real Python и Medium (2020+). Тестирование пайплайнов.
- **"Data Pipeline Design Patterns"** — статьи на Towards Data Science (2021+). Паттерны проектирования.

### Мониторинг и логирование
- **"Prometheus: Up & Running"** — Brian Brazil (2018). Практический учебник по мониторингу.
- **"Grafana Documentation"** — Grafana Labs (https://grafana.com/docs/). Создание дашбордов.
- **"Structured Logging: The Best Practice You're Missing"** — статьи на Medium (2019+). Логирование в пайплайнах.
- **"Data Observability: The Next Frontier of Data Engineering"** — статьи на Towards Data Science (2021+). Наблюдаемость данных.

### Обработка ошибок и восстановление
- **"Error Handling in Data Pipelines"** — статьи на Real Python и Medium (2020+). Стратегии обработки ошибок.
- **"Resilient Systems Design"** — статьи на блогах инженеров (2019+). Проектирование устойчивых систем.
- **"Dead Letter Queues and Error Handling"** — статьи на Kafka и RabbitMQ документации (2020+). Обработка ошибок в потоках.
- **"Self-Healing Systems"** — статьи на Medium (2021+). Автоматическое восстановление.

---

## Современные хранилища данных

### Data Lakes vs Data Warehouses
- **"The Data Warehouse Toolkit"** — Ralph Kimball, Margy Ross (3-е издание, 2013). Классический учебник о хранилищах.
- **"Data Lake Architecture: Designing the Data Lake and Avoiding the Garbage Dump"** — Bill Inmon (2016). Архитектура озер данных.
- **"The Lakehouse: Data Warehouses and Data Lakes"** — Matei Zaharia et al. (2021). Гибридный подход.
- **"Designing Modern Data Warehouses"** — статьи на Towards Data Science (2021+). Современный дизайн хранилищ.

### Колоночные базы данных
- **"ClickHouse Official Documentation"** — ClickHouse Team (https://clickhouse.com/docs/). Полная документация.
- **"BigQuery: The Definitive Guide"** — Valliappa Lakshmanan, Sravya Shetty (2020). Практический учебник по BigQuery.
- **"Apache Druid: A Real-Time OLAP Datastore"** — Druid Team (https://druid.apache.org/). Документация Druid.
- **"Snowflake: The Elastic Data Warehouse"** — Snowflake Documentation (https://docs.snowflake.com/). Полное руководство.

### NoSQL решения
- **"MongoDB: The Definitive Guide"** — Shannon Bradshaw, Scott Mcowan, Elyse Greenfield (3-е издание, 2019). Полное руководство по MongoDB.
- **"Cassandra: The Definitive Guide"** — Eben Hewitt (3-е издание, 2020). Практический учебник по Cassandra.
- **"Elasticsearch: The Definitive Guide"** — Clinton Gormley, Zachary Tong (2015). Поиск и аналитика.
- **"Graph Databases: New Opportunities for Connected Data"** — Ian Robinson, Jim Webber, Emil Eifrem (2-е издание, 2015). Графовые базы данных.

### Распределенные файловые системы
- **"Delta Lake: High-Performance ACID Table Storage over Cloud Object Stores"** — Delta Lake Team (https://delta.io/). Документация Delta Lake.
- **"Apache Iceberg: An Open Table Format for Huge Analytic Tables"** — Iceberg Team (https://iceberg.apache.org/). Документация Iceberg.
- **"Apache Hudi: Incremental Processing Framework for Big Data"** — Hudi Team (https://hudi.apache.org/). Документация Hudi.
- **"HDFS Architecture Guide"** — Apache Hadoop Team (https://hadoop.apache.org/). Архитектура распределенной файловой системы.

---

## Мониторинг, тестирование и DevOps

### Data observability и мониторинг качества
- **"Data Observability: The Next Frontier of Data Engineering"** — статьи на Towards Data Science (2021+). Концепция наблюдаемости данных.
- **"Great Expectations: Always Know What to Expect from Your Data"** — Great Expectations Team (https://greatexpectations.io/). Валидация и мониторинг.
- **"Data Quality Dimensions and Metrics"** — статьи на Medium (2020+). Метрики качества данных.
- **"Data Lineage and Governance"** — статьи на Towards Data Science (2021+). Отслеживание происхождения данных.

### Тестирование пайплайнов данных
- **"Testing Data Pipelines"** — статьи на Real Python и Medium (2020+). Практический подход к тестированию.
- **"Pytest Documentation"** — Pytest Team (https://docs.pytest.org/). Фреймворк для тестирования Python.
- **"Test-Driven Data Analysis"** — статьи на Towards Data Science (2020+). TDD для анализа данных.
- **"Integration Testing for Data Pipelines"** — статьи на блогах инженеров (2021+). Интеграционное тестирование.

### CI/CD для проектов с данными
- **"Infrastructure as Code: Managing Servers in the Cloud"** — Kief Morris (2-е издание, 2020). Инфраструктура как код.
- **"GitOps and Kubernetes"** — статьи на The New Stack (2020+). GitOps подход.
- **"Continuous Integration and Continuous Deployment for Data Pipelines"** — статьи на Towards Data Science (2021+). CI/CD для данных.
- **"GitHub Actions Documentation"** — GitHub Team (https://docs.github.com/en/actions). Автоматизация рабочих процессов.

### Безопасность и соответствие требованиям
- **"GDPR Compliance: A Practical Guide"** — статьи на блогах и официальных источниках (2020+). Соответствие GDPR.
- **"Data Security and Privacy in the Cloud"** — статьи на AWS и Azure блогах (2021+). Безопасность облачных данных.
- **"Data Governance Best Practices"** — статьи на Towards Data Science (2021+). Управление данными.
- **"Role-Based Access Control (RBAC) Implementation"** — статьи на Medium и документация платформ (2020+). Управление доступом.