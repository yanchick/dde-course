---
marp: true
theme: default
size: 16:9
paginate: true
math: katex
---
# Лекция 7: Современные хранилища данных


## Слайд 1: Титульный слайд

# Современные хранилища данных

**Лекция 7**

- Реляционные БД и SQL
- Data Lakes vs Data Warehouses
- Колоночные базы данных
- NoSQL решения
- Распределенные файловые системы

---

## Слайд 2: План лекции

### Структура лекции

1. **Реляционные БД и SQL** (20 мин)
2. **Data Lakes vs Data Warehouses** (15 мин)
3. **Колоночные базы данных** (15 мин)
4. **NoSQL решения** (20 мин)
5. **Распределенные файловые системы** (10 мин)

---

## РАЗДЕЛ 1: Реляционные БД и SQL

---

## Слайд 3: Введение в реляционные БД

### Что такое реляционная база данных?

- Данные организованы в **таблицы** (relations)
- Строки = записи, столбцы = атрибуты
- Связи между таблицами через **ключи**
- Строгая схема данных (schema-on-write)
- Гарантии ACID для транзакций

---

## Слайд 4: ACID свойства

### Гарантии надежности транзакций

- **A**tomicity - атомарность операций
- **C**onsistency - согласованность данных
- **I**solation - изолированность транзакций
- **D**urability - долговечность результатов

**Пример:** Банковский перевод между счетами

---

## Слайд 5: Архитектура РСУБД

```mermaid
graph LR
    Client[Клиентское приложение]
    Parser[SQL Parser]
    Optimizer[Query Optimizer]
    Executor[Execution Engine]
    Storage[Storage Engine]
    Buffer[Buffer Pool]
    Disk[(Диск)]
    
    Client -->|SQL запрос| Parser
    Parser -->|Синтаксическое дерево| Optimizer
    Optimizer -->|План выполнения| Executor
    Executor <-->|Чтение/Запись| Buffer
    Buffer <-->|Страницы данных| Storage
    Storage <-->|Физические блоки| Disk
    
    style Client fill:#e1f5ff
    style Optimizer fill:#fff4e1
    style Storage fill:#e8f5e9
```

**Основные компоненты:** Parser → Optimizer → Executor → Storage

---

## Слайд 6: Популярные РСУБД

### Основные представители

- **PostgreSQL** - открытая, расширяемая, JSONB
- **MySQL** - популярная, быстрая, веб-приложения
- **Oracle** - enterprise, производительность, стоимость
- **MS SQL Server** - интеграция с Microsoft
- **SQLite** - встраиваемая, мобильные приложения

---

## Слайд 7: Основы SQL - DDL

### Data Definition Language

```sql
-- Создание таблицы
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Изменение структуры
ALTER TABLE users ADD COLUMN last_login TIMESTAMP;

-- Удаление таблицы
DROP TABLE users;
```

---

## Слайд 8: Основы SQL - DML

### Data Manipulation Language

```sql
-- Вставка данных
INSERT INTO users (username, email) 
VALUES ('john_doe', 'john@example.com');

-- Обновление данных
UPDATE users SET last_login = NOW() 
WHERE username = 'john_doe';

-- Удаление данных
DELETE FROM users WHERE user_id = 5;
```

---

## Слайд 9: Основы SQL - DQL

### Data Query Language

```sql
-- Простая выборка
SELECT username, email FROM users;

-- Фильтрация
SELECT * FROM users WHERE created_at > '2024-01-01';

-- Сортировка
SELECT * FROM users ORDER BY created_at DESC LIMIT 10;

-- Агрегация
SELECT COUNT(*) as total_users FROM users;
```

---

## Слайд 10: SQL JOIN операции

```mermaid
graph LR
    subgraph "Типы JOIN"
        A[INNER JOIN]
        B[LEFT JOIN]
        C[RIGHT JOIN]
        D[FULL OUTER JOIN]
        E[CROSS JOIN]
    end
    
    A --> F[Только совпадения]
    B --> G[Все из левой + совпадения]
    C --> H[Все из правой + совпадения]
    D --> I[Все записи из обеих таблиц]
    E --> J[Декартово произведение]
    
    style A fill:#4CAF50
    style B fill:#2196F3
    style C fill:#FF9800
    style D fill:#9C27B0
    style E fill:#F44336
```

---

## Слайд 11: Примеры JOIN

### Объединение таблиц

```sql
-- INNER JOIN
SELECT u.username, o.order_id, o.total
FROM users u
INNER JOIN orders o ON u.user_id = o.user_id;

-- LEFT JOIN
SELECT u.username, COUNT(o.order_id) as order_count
FROM users u
LEFT JOIN orders o ON u.user_id = o.user_id
GROUP BY u.username;
```

---

## Слайд 12: Индексы в РСУБД

### Ускорение поиска данных

- **B-Tree** индексы - универсальные, по умолчанию
- **Hash** индексы - только для равенства
- **GiST/GIN** - полнотекстовый поиск, JSON
- **Bitmap** индексы - низкая кардинальность
- Компромисс: скорость чтения vs запись

---

## Слайд 13: Создание индексов

```sql
-- Простой индекс
CREATE INDEX idx_username ON users(username);

-- Составной индекс
CREATE INDEX idx_user_date 
ON orders(user_id, order_date);

-- Уникальный индекс
CREATE UNIQUE INDEX idx_email ON users(email);

-- Частичный индекс
CREATE INDEX idx_active_users 
ON users(username) WHERE is_active = true;
```

---

## Слайд 14: Нормализация БД

```mermaid
graph LR
    A[Ненормализованная форма] -->|Устранение повторяющихся групп| B[1NF]
    B -->|Устранение частичных зависимостей| C[2NF]
    C -->|Устранение транзитивных зависимостей| D[3NF]
    D -->|Устранение многозначных зависимостей| E[BCNF]
    E -->|Дальнейшая декомпозиция| F[4NF, 5NF]
    
    style A fill:#ffcdd2
    style B fill:#fff9c4
    style C fill:#c8e6c9
    style D fill:#b2dfdb
    style E fill:#b3e5fc
    style F fill:#e1bee7
```

**На практике:** Обычно достаточно 3NF

---

## Слайд 15: Пример нормализации

### Ненормализованная таблица

```sql
CREATE TABLE orders_bad (
    order_id INT,
    customer_name VARCHAR(100),
    customer_email VARCHAR(100),
    product_names TEXT, -- "Laptop, Mouse, Keyboard"
    product_prices TEXT -- "1000, 25, 75"
);
```

**Проблемы:** Повторение данных клиента, списки в полях

---

## Слайд 16: Нормализованная структура

### 3NF схема

```sql
CREATE TABLE customers (
    customer_id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100) UNIQUE
);

CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    price DECIMAL(10,2)
);

CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    customer_id INT REFERENCES customers(customer_id),
    order_date TIMESTAMP
);

CREATE TABLE order_items (
    order_id INT REFERENCES orders(order_id),
    product_id INT REFERENCES products(product_id),
    quantity INT,
    PRIMARY KEY (order_id, product_id)
);
```

---

## Слайд 17: Денормализация

### Когда нарушать правила?

- **Производительность** - меньше JOIN'ов
- **Аналитические запросы** - предагрегированные данные
- **Кэширование** - материализованные представления
- **OLAP системы** - звезда, снежинка
- Компромисс: скорость vs избыточность

---

## Слайд 18: Транзакции и изоляция

### Уровни изоляции

```sql
-- Начало транзакции
BEGIN;

-- Установка уровня изоляции
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;

-- Операции
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;

-- Фиксация или откат
COMMIT; -- или ROLLBACK;
```

---

## Слайд 19: Уровни изоляции

```mermaid
graph TB
    A[Read Uncommitted]
    B[Read Committed]
    C[Repeatable Read]
    D[Serializable]
    
    A -->|Dirty Reads| E[Наименьшая изоляция]
    B -->|Предотвращает Dirty Reads| F[PostgreSQL по умолчанию]
    C -->|Предотвращает Non-repeatable Reads| G[MySQL InnoDB по умолчанию]
    D -->|Полная изоляция| H[Наибольшая изоляция]
    
    style A fill:#ffcdd2
    style B fill:#fff9c4
    style C fill:#c8e6c9
    style D fill:#b2dfdb
```

**Выбор зависит от:** требований к консистентности vs производительности

---

## Слайд 20: Оптимизация запросов

### Инструменты анализа

```sql
-- План выполнения запроса
EXPLAIN ANALYZE
SELECT u.username, COUNT(o.order_id)
FROM users u
LEFT JOIN orders o ON u.user_id = o.user_id
WHERE u.created_at > '2024-01-01'
GROUP BY u.username;
```

**Обращайте внимание на:**
- Seq Scan vs Index Scan
- Nested Loop vs Hash Join
- Время выполнения

---

## Слайд 21: Вопрос для проверки 1

### Проверьте себя

**Вопрос:** Какой тип JOIN вернет все записи из левой таблицы, даже если нет совпадений в правой?

A) INNER JOIN  
B) LEFT JOIN  
C) RIGHT JOIN  
D) CROSS JOIN

---

## Слайд 22: Вопрос для проверки 2

### Проверьте себя

**Вопрос:** Какое свойство ACID гарантирует, что транзакция либо выполнится полностью, либо не выполнится вообще?

A) Atomicity  
B) Consistency  
C) Isolation  
D) Durability

---

## Слайд 23: Резюме раздела 1

### Реляционные БД и SQL

- **Структура:** Таблицы, связи, схемы
- **ACID:** Надежность транзакций
- **SQL:** DDL, DML, DQL операции
- **Индексы:** Ускорение поиска данных
- **Нормализация:** Устранение избыточности
- **Оптимизация:** EXPLAIN, правильные индексы

---

## РАЗДЕЛ 2: Data Lakes vs Data Warehouses

---

## Слайд 24: Эволюция хранилищ

```mermaid
timeline
    title Эволюция хранилищ данных
    1980s : Реляционные БД
          : OLTP системы
    1990s : Data Warehouses
          : OLAP кубы
    2000s : Hadoop
          : Big Data
    2010s : Data Lakes
          : Schema-on-Read
    2020s : Data Lakehouses
          : Unified Analytics
```

---

## Слайд 25: Data Warehouse

### Хранилище данных

- **Структурированные** данные с четкой схемой
- Оптимизировано для **аналитических** запросов
- **ETL** процессы для загрузки
- **Schema-on-Write** - схема при записи
- **Высокая производительность** для BI

---

## Слайд 26: Архитектура DWH

```mermaid
graph LR
    subgraph Sources
        A1[(OLTP DB)]
        A2[(CRM)]
        A3[(ERP)]
    end
    
    subgraph ETL
        B[Extract]
        C[Transform]
        D[Load]
    end
    
    subgraph DWH
        E[(Staging Area)]
        F[(Data Warehouse)]
        G[Data Marts]
    end
    
    subgraph Consumers
        H[BI Tools]
        I[Reports]
        J[Dashboards]
    end
    
    A1 --> B
    A2 --> B
    A3 --> B
    B --> C
    C --> D
    D --> E
    E --> F
    F --> G
    G --> H
    G --> I
    G --> J
    
    style F fill:#4CAF50
    style G fill:#2196F3
```

---

## Слайд 27: Схемы DWH - Звезда

```mermaid
graph TD
    F[Fact Table<br/>Sales]
    D1[Dim: Time]
    D2[Dim: Product]
    D3[Dim: Customer]
    D4[Dim: Store]
    
    F --- D1
    F --- D2
    F --- D3
    F --- D4
    
    style F fill:#FF9800
    style D1 fill:#4CAF50
    style D2 fill:#4CAF50
    style D3 fill:#4CAF50
    style D4 fill:#4CAF50
```

**Преимущества:** Простота, производительность JOIN'ов

---

## Слайд 28: Схемы DWH - Снежинка

```mermaid
graph TD
    F[Fact Table<br/>Sales]
    D1[Dim: Date]
    D2[Dim: Product]
    D3[Dim: Customer]
    
    D1_1[Month]
    D1_2[Quarter]
    D1_3[Year]
    
    D2_1[Category]
    D2_2[Subcategory]
    
    D3_1[City]
    D3_2[Country]
    
    F --- D1
    F --- D2
    F --- D3
    
    D1 --- D1_1
    D1_1 --- D1_2
    D1_2 --- D1_3
    
    D2 --- D2_1
    D2_1 --- D2_2
    
    D3 --- D3_1
    D3_1 --- D3_2
    
    style F fill:#FF9800
    style D1 fill:#4CAF50
    style D2 fill:#4CAF50
    style D3 fill:#4CAF50
```

**Преимущества:** Нормализация, меньше избыточности

---

## Слайд 29: Data Lake

### Озеро данных

- **Любые типы** данных (структурированные, неструктурированные)
- Хранение в **сыром виде**
- **Schema-on-Read** - схема при чтении
- **Масштабируемость** для петабайтов
- Гибкость для **ML и исследований**

---

## Слайд 30: Архитектура Data Lake

```mermaid
graph TB
    subgraph Sources
        S1[IoT Sensors]
        S2[Logs]
        S3[Databases]
        S4[APIs]
        S5[Files]
    end
    
    subgraph Ingestion
        I1[Batch]
        I2[Streaming]
    end
    
    subgraph Lake Zones
        Z1[Raw Zone<br/>Сырые данные]
        Z2[Processed Zone<br/>Очищенные данные]
        Z3[Curated Zone<br/>Бизнес-данные]
    end
    
    subgraph Consumers
        C1[Data Scientists]
        C2[Analysts]
        C3[ML Models]
        C4[Applications]
    end
    
    S1 & S2 --> I2
    S3 & S4 & S5 --> I1
    I1 & I2 --> Z1
    Z1 --> Z2
    Z2 --> Z3
    Z3 --> C1 & C2 & C3 & C4
    
    style Z1 fill:#ffcdd2
    style Z2 fill:#fff9c4
    style Z3 fill:#c8e6c9
```

---

## Слайд 31: Зоны Data Lake

### Организация данных

- **Raw/Bronze** - сырые данные как есть
- **Processed/Silver** - очищенные, валидированные
- **Curated/Gold** - бизнес-агрегаты, витрины
- **Sandbox** - экспериментальная зона
- **Archive** - исторические данные

---

## Слайд 32: Data Lakehouse

### Лучшее из двух миров

- **ACID транзакции** как в DWH
- **Гибкость схемы** как в Data Lake
- **Производительность** для аналитики
- **Единая платформа** для всех данных
- Технологии: Delta Lake, Apache Iceberg, Apache Hudi

---

## Слайд 33: Сравнение подходов

```mermaid
graph TB
    subgraph "Data Warehouse"
        DW1[Структурированные данные]
        DW2[Schema-on-Write]
        DW3[Высокая производительность]
        DW4[BI и отчетность]
        DW5[Высокая стоимость]
    end
    
    subgraph "Data Lake"
        DL1[Любые типы данных]
        DL2[Schema-on-Read]
        DL3[Масштабируемость]
        DL4[ML и исследования]
        DL5[Низкая стоимость]
    end
    
    subgraph "Data Lakehouse"
        LH1[Объединяет преимущества]
        LH2[ACID + Гибкость]
        LH3[Универсальная платформа]
    end
    
    DW1 & DW2 & DW3 & DW4 --> LH1
    DL1 & DL2 & DL3 & DL4 --> LH1
    LH1 --> LH2 --> LH3
    
    style DW1 fill:#4CAF50
    style DL1 fill:#2196F3
    style LH1 fill:#9C27B0
```

---

## Слайд 34: Метаданные и каталоги

### Управление знаниями о данных

- **Data Catalog** - каталог всех датасетов
- **Lineage** - происхождение и трансформации
- **Schema Registry** - версионирование схем
- **Data Discovery** - поиск нужных данных
- Инструменты: Apache Atlas, AWS Glue, Alation

---

## Слайд 35: Вопрос для проверки 3

### Проверьте себя

**Вопрос:** В какой зоне Data Lake хранятся сырые, необработанные данные?

A) Curated Zone  
B) Processed Zone  
C) Raw Zone  
D) Sandbox

---

## Слайд 36: Резюме раздела 2

### Data Lakes vs Data Warehouses

- **DWH:** Структура, производительность, BI
- **Data Lake:** Гибкость, масштабируемость, ML
- **Lakehouse:** Объединение преимуществ
- **Схемы:** Звезда, снежинка для DWH
- **Зоны:** Raw → Processed → Curated
- **Метаданные:** Каталоги, lineage, discovery

---

## РАЗДЕЛ 3: Колоночные базы данных

---

## Слайд 37: Строковое vs Колоночное хранение

```mermaid
graph TB
    subgraph "Row-Oriented (OLTP)"
        R1[Row 1: id=1, name=Alice, age=25, city=NY]
        R2[Row 2: id=2, name=Bob, age=30, city=LA]
        R3[Row 3: id=3, name=Charlie, age=35, city=SF]
    end
    
    subgraph "Column-Oriented (OLAP)"
        C1[id: 1, 2, 3]
        C2[name: Alice, Bob, Charlie]
        C3[age: 25, 30, 35]
        C4[city: NY, LA, SF]
    end
    
    style R1 fill:#ffcdd2
    style R2 fill:#ffcdd2
    style R3 fill:#ffcdd2
    style C1 fill:#c8e6c9
    style C2 fill:#c8e6c9
    style C3 fill:#c8e6c9
    style C4 fill:#c8e6c9
```

**Запрос:** `SELECT AVG(age) FROM users;`  
**Колоночное:** Читает только столбец `age`

---

## Слайд 38: Преимущества колоночного хранения

### Почему быстрее для аналитики?

- **Компрессия** - похожие данные сжимаются лучше
- **I/O оптимизация** - читаем только нужные столбцы
- **Векторизация** - параллельная обработка
- **Агрегации** - быстрые SUM, AVG, COUNT
- **Партиционирование** - по столбцам и строкам

---

## Слайд 39: ClickHouse - обзор

### Быстрая колоночная СУБД

- Разработана **Яндексом** для аналитики
- **Open Source** под Apache 2.0
- **Скорость:** миллиарды строк в секунду
- **SQL** совместимость
- **Горизонтальное** масштабирование

---

## Слайд 40: ClickHouse - архитектура

```mermaid
graph TB
    subgraph Cluster
        N1[Node 1]
        N2[Node 2]
        N3[Node 3]
    end
    
    subgraph "Node 1 Structure"
        T1[Table Engine]
        P1[Partitions]
        I1[Indexes]
        C1[Compression]
    end
    
    ZK[ZooKeeper<br/>Координация]
    
    Client[Client] -->|SQL Query| N1
    N1 <-->|Репликация| N2
    N2 <-->|Репликация| N3
    N3 <-->|Репликация| N1
    
    N1 --> T1
    T1 --> P1 & I1 & C1
    
    N1 & N2 & N3 <-->|Метаданные| ZK
    
    style N1 fill:#4CAF50
    style N2 fill:#4CAF50
    style N3 fill:#4CAF50
    style ZK fill:#FF9800
```

---

## Слайд 41: ClickHouse - типы таблиц

### Table Engines

```sql
-- MergeTree - основной движок
CREATE TABLE events (
    date Date,
    user_id UInt32,
    event_type String,
    value Float64
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, user_id);

-- ReplicatedMergeTree - с репликацией
CREATE TABLE events_replicated (
    -- ... поля ...
) ENGINE = ReplicatedMergeTree('/clickhouse/tables/events', '{replica}')
PARTITION BY toYYYYMM(date)
ORDER BY (date, user_id);
```

---

## Слайд 42: ClickHouse - материализованные представления

```sql
-- Создание материализованного представления
CREATE MATERIALIZED VIEW daily_stats
ENGINE = SummingMergeTree()
PARTITION BY toYYYYMM(date)
ORDER BY (date, event_type)
AS SELECT
    date,
    event_type,
    count() as event_count,
    sum(value) as total_value
FROM events
GROUP BY date, event_type;
```

**Преимущество:** Предагрегированные данные для быстрых запросов

---

## Слайд 43: BigQuery - обзор

### Serverless Data Warehouse от Google

- **Полностью управляемый** сервис
- **Автоматическое масштабирование**
- **Оплата за запросы** (on-demand или flat-rate)
- **Интеграция** с GCP экосистемой
- **ML встроенный** (BigQuery ML)

---

## Слайд 44: BigQuery - архитектура

```mermaid
graph TB
    subgraph "Compute Layer"
        Q[Query Executor]
        S[Scheduler]
    end
    
    subgraph "Storage Layer (Colossus)"
        D1[Dataset 1]
        D2[Dataset 2]
        D3[Dataset 3]
    end
    
    subgraph "Metadata Layer"
        M[Dremel Metadata]
        C[Catalog]
    end
    
    Client[Client] -->|SQL| Q
    Q --> S
    S -->|Parallel Execution| D1 & D2 & D3
    Q <--> M
    M <--> C
    
    style Q fill:#4285F4
    style D1 fill:#34A853
    style D2 fill:#34A853
    style D3 fill:#34A853
    style M fill:#FBBC04
```

**Разделение:** Вычисления и хранение независимы

---

## Слайд 45: BigQuery - партиционирование

```sql
-- Партиционирование по дате
CREATE TABLE mydataset.events
PARTITION BY DATE(event_timestamp)
AS SELECT
    event_timestamp,
    user_id,
    event_type,
    value
FROM source_table;

-- Партиционирование по целому числу
CREATE TABLE mydataset.users
PARTITION BY RANGE_BUCKET(user_id, GENERATE_ARRAY(0, 1000000, 10000))
AS SELECT * FROM source_users;
```

**Преимущество:** Сканирование только нужных партиций

---

## Слайд 46: BigQuery - кластеризация

```sql
-- Кластеризация для оптимизации запросов
CREATE TABLE mydataset.events
PARTITION BY DATE(event_timestamp)
CLUSTER BY user_id, event_type
AS SELECT
    event_timestamp,
    user_id,
    event_type,
    value
FROM source_table;
```

**Эффект:** Данные физически сортируются по указанным столбцам

---

## Слайд 47: Оптимизация запросов

### Лучшие практики

- **Избегайте SELECT *** - выбирайте только нужные столбцы
- **Используйте партиции** - WHERE DATE(ts) = '2024-01-01'
- **Денормализуйте** - меньше JOIN'ов
- **Материализованные представления** - предагрегация
- **Анализируйте стоимость** - EXPLAIN и Query Plan

---

## Слайд 48: Вопрос для проверки 4

### Проверьте себя

**Вопрос:** Почему колоночные БД быстрее для аналитических запросов?

A) Хранят меньше данных  
B) Читают только нужные столбцы  
C) Не поддерживают JOIN  
D) Используют быстрые диски

---

## Слайд 49: Резюме раздела 3

### Колоночные базы данных

- **Принцип:** Хранение по столбцам, не по строкам
- **Преимущества:** Компрессия, I/O, агрегации
- **ClickHouse:** Open source, очень быстрый
- **BigQuery:** Serverless, автомасштабирование
- **Оптимизация:** Партиции, кластеризация, индексы
- **Применение:** OLAP, аналитика, отчетность

---

## РАЗДЕЛ 4: NoSQL решения

---

## Слайд 50: Теорема CAP

```mermaid
graph TD
    CAP[CAP Theorem]
    
    C[Consistency<br/>Согласованность]
    A[Availability<br/>Доступность]
    P[Partition Tolerance<br/>Устойчивость к разделению]
    
    CAP --> C
    CAP --> A
    CAP --> P
    
    CP[CP Systems<br/>MongoDB, HBase]
    AP[AP Systems<br/>Cassandra, DynamoDB]
    CA[CA Systems<br/>RDBMS<br/>Нереалистично в распределенных системах]
    
    C & P --> CP
    A & P --> AP
    C & A --> CA
    
    style CAP fill:#9C27B0
    style C fill:#4CAF50
    style A fill:#2196F3
    style P fill:#FF9800
    style CP fill:#c8e6c9
    style AP fill:#b3e5fc
    style CA fill:#ffcdd2
```

**Выбирайте 2 из 3**

---

## Слайд 51: Типы NoSQL БД

```mermaid
graph TB
    NoSQL[NoSQL Databases]
    
    D[Document<br/>MongoDB, CouchDB]
    KV[Key-Value<br/>Redis, DynamoDB]
    C[Column-Family<br/>Cassandra, HBase]
    G[Graph<br/>Neo4j, ArangoDB]
    
    NoSQL --> D
    NoSQL --> KV
    NoSQL --> C
    NoSQL --> G
    
    D --> D1[Гибкая схема<br/>JSON документы]
    KV --> KV1[Простота<br/>Высокая скорость]
    C --> C1[Масштабируемость<br/>Большие данные]
    G --> G1[Связи<br/>Графовые запросы]
    
    style D fill:#4CAF50
    style KV fill:#2196F3
    style C fill:#FF9800
    style G fill:#9C27B0
```

---

## Слайд 52: MongoDB - обзор

### Документо-ориентированная БД

- **JSON/BSON** документы
- **Гибкая схема** - разные поля в документах
- **Индексы** на любые поля
- **Агрегации** - мощный pipeline
- **Репликация** и шардирование

---

## Слайд 53: MongoDB - структура данных

```javascript
// Пример документа
{
  "_id": ObjectId("507f1f77bcf86cd799439011"),
  "username": "john_doe",
  "email": "john@example.com",
  "profile": {
    "firstName": "John",
    "lastName": "Doe",
    "age": 30
  },
  "interests": ["coding", "music", "travel"],
  "orders": [
    { "orderId": 1, "total": 99.99, "date": ISODate("2024-01-15") },
    { "orderId": 2, "total": 149.99, "date": ISODate("2024-02-20") }
  ]
}
```

**Преимущество:** Вложенные структуры без JOIN'ов

---

## Слайд 54: MongoDB - агрегации

```javascript
// Aggregation Pipeline
db.orders.aggregate([
  // Фильтрация
  { $match: { status: "completed" } },
  
  // Группировка
  { $group: {
      _id: "$customerId",
      totalSpent: { $sum: "$total" },
      orderCount: { $sum: 1 }
  }},
  
  // Сортировка
  { $sort: { totalSpent: -1 } },
  
  // Ограничение
  { $limit: 10 }
]);
```

---

## Слайд 55: Cassandra - обзор

### Распределенная колоночная БД

- **Линейная масштабируемость**
- **Отказоустойчивость** - нет single point of failure
- **Настраиваемая консистентность**
- **CQL** - язык похожий на SQL
- **Write-оптимизированная** архитектура

---

## Слайд 56: Cassandra - архитектура

```mermaid
graph TB
    subgraph "Cassandra Cluster"
        N1[Node 1<br/>Token Range: 0-25]
        N2[Node 2<br/>Token Range: 26-50]
        N3[Node 3<br/>Token Range: 51-75]
        N4[Node 4<br/>Token Range: 76-100]
    end
    
    Client[Client]
    
    Client -->|Write/Read| N1
    N1 <-->|Gossip| N2
    N2 <-->|Gossip| N3
    N3 <-->|Gossip| N4
    N4 <-->|Gossip| N1
    
    N1 -->|Replica| N2
    N2 -->|Replica| N3
    N3 -->|Replica| N4
    
    style N1 fill:#4CAF50
    style N2 fill:#4CAF50
    style N3 fill:#4CAF50
    style N4 fill:#4CAF50
```

**Peer-to-peer:** Все узлы равноправны

---

## Слайд 57: Cassandra - модель данных

```sql
-- Создание keyspace
CREATE KEYSPACE ecommerce 
WITH replication = {
  'class': 'SimpleStrategy',
  'replication_factor': 3
};

-- Создание таблицы
CREATE TABLE ecommerce.orders (
    user_id UUID,
    order_date timestamp,
    order_id UUID,
    total decimal,
    status text,
    PRIMARY KEY (user_id, order_date, order_id)
) WITH CLUSTERING ORDER BY (order_date DESC);
```

**Ключ:** Partition key + Clustering columns

---

## Слайд 58: Redis - обзор

### In-Memory Key-Value Store

- **Структуры данных:** Strings, Lists, Sets, Hashes, Sorted Sets
- **Персистентность:** RDB snapshots, AOF logs
- **Pub/Sub** для обмена сообщениями
- **Redis Streams** для event sourcing
- **Кластеризация** и репликация

---

## Слайд 59: Redis - структуры данных

```python
import redis

r = redis.Redis(host='localhost', port=6379)

# Strings
r.set('user:1000:name', 'John Doe')
r.get('user:1000:name')

# Hashes
r.hset('user:1000', mapping={
    'name': 'John Doe',
    'email': 'john@example.com',
    'age': 30
})

# Lists
r.lpush('queue:tasks', 'task1', 'task2', 'task3')

# Sorted Sets (leaderboard)
r.zadd('leaderboard', {'player1': 1000, 'player2': 1500})
```

---

## Слайд 60: Neo4j - графовая БД

### Работа со связями

```cypher
// Создание узлов и связей
CREATE (alice:Person {name: 'Alice', age: 30})
CREATE (bob:Person {name: 'Bob', age: 35})
CREATE (company:Company {name: 'TechCorp'})
CREATE (alice)-[:WORKS_AT {since: 2020}]->(company)
CREATE (bob)-[:WORKS_AT {since: 2018}]->(company)
CREATE (alice)-[:KNOWS {since: 2015}]->(bob)

// Запрос: Найти коллег Alice
MATCH (alice:Person {name: 'Alice'})-[:WORKS_AT]->(c:Company)
      <-[:WORKS_AT]-(colleague:Person)
RETURN colleague.name
```

---

## Слайд 61: Выбор NoSQL решения

```mermaid
graph TD
    Start[Выбор NoSQL БД]
    
    Q1{Тип данных?}
    Q2{Связи важны?}
    Q3{Скорость записи?}
    Q4{In-memory?}
    
    Start --> Q1
    Q1 -->|Документы| MongoDB
    Q1 -->|Графы| Q2
    Q1 -->|Временные ряды| Q3
    Q1 -->|Кэш/Сессии| Q4
    
    Q2 -->|Да| Neo4j
    Q2 -->|Нет| MongoDB
    
    Q3 -->|Критична| Cassandra
    Q3 -->|Средняя| ClickHouse
    
    Q4 -->|Да| Redis
    Q4 -->|Нет| MongoDB
    
    style MongoDB fill:#4CAF50
    style Neo4j fill:#9C27B0
    style Cassandra fill:#FF9800
    style Redis fill:#2196F3
    style ClickHouse fill:#00BCD4
```

---

## Слайд 62: Вопрос для проверки 5

### Проверьте себя

**Вопрос:** Какая NoSQL БД лучше всего подходит для хранения социального графа с множеством связей?

A) MongoDB  
B) Redis  
C) Cassandra  
D) Neo4j

---

## Слайд 63: Резюме раздела 4

### NoSQL решения

- **Типы:** Document, Key-Value, Column-Family, Graph
- **CAP теорема:** Выбор между C, A, P
- **MongoDB:** Гибкие документы, агрегации
- **Cassandra:** Масштабируемость, write-оптимизация
- **Redis:** In-memory, структуры данных
- **Neo4j:** Графы и связи

---

## РАЗДЕЛ 5: Распределенные файловые системы

---

## Слайд 64: HDFS - архитектура

```mermaid
graph TB
    Client[HDFS Client]
    NN[NameNode<br/>Метаданные]
    SNN[Secondary NameNode<br/>Backup]
    
    DN1[DataNode 1<br/>Блоки данных]
    DN2[DataNode 2<br/>Блоки данных]
    DN3[DataNode 3<br/>Блоки данных]
    
    Client -->|Запрос метаданных| NN
    Client -->|Чтение/Запись| DN1 & DN2 & DN3
    
    NN <-->|Heartbeat| DN1 & DN2 & DN3
    NN <-->|Checkpoint| SNN
    
    DN1 <-->|Репликация| DN2
    DN2 <-->|Репликация| DN3
    DN3 <-->|Репликация| DN1
    
    style NN fill:#FF9800
    style SNN fill:#FFC107
    style DN1 fill:#4CAF50
    style DN2 fill:#4CAF50
    style DN3 fill:#4CAF50
```

---

## Слайд 65: Amazon S3 - обзор

### Object Storage

- **Объектное хранилище** - не файловая система
- **Бесконечная масштабируемость**
- **Классы хранения:** Standard, IA, Glacier
- **Версионирование** и жизненный цикл
- **Интеграция** с AWS сервисами

---

## Слайд 66: S3 - классы хранения

```mermaid
graph LR
    S3[Amazon S3]
    
    STD[Standard<br/>Частый доступ<br/>$$$]
    IA[Infrequent Access<br/>Редкий доступ<br/>$$]
    GL[Glacier<br/>Архив<br/>$]
    DGL[Deep Glacier<br/>Долгий архив<br/>¢]
    
    S3 --> STD
    S3 --> IA
    S3 --> GL
    S3 --> DGL
    
    STD -->|Lifecycle Policy| IA
    IA -->|Lifecycle Policy| GL
    GL -->|Lifecycle Policy| DGL
    
    style STD fill:#4CAF50
    style IA fill:#2196F3
    style GL fill:#FF9800
    style DGL fill:#9C27B0
```

**Выбор зависит от:** частоты доступа и требований к latency

---

## Слайд 67: Delta Lake - ACID на озере

### Транзакционный слой

- **ACID транзакции** на S3/HDFS
- **Time Travel** - версионирование данных
- **Schema Evolution** - изменение схем
- **Upserts и Deletes** - обновление данных
- **Streaming + Batch** в одной таблице

---

## Слайд 68: Delta Lake - пример

```python
from delta import *

# Создание Delta таблицы
df = spark.read.json("s3://bucket/raw-data/")
df.write.format("delta").save("s3://bucket/delta/events")

# Time Travel
df_yesterday = spark.read.format("delta") \
    .option("versionAsOf", 1) \
    .load("s3://bucket/delta/events")

# Upsert (Merge)
deltaTable = DeltaTable.forPath(spark, "s3://bucket/delta/events")
deltaTable.alias("target").merge(
    updates.alias("source"),
    "target.id = source.id"
).whenMatchedUpdateAll() \
 .whenNotMatchedInsertAll() \
 .execute()
```

---

## Слайд 69: Форматы файлов

### Оптимизация хранения

- **Parquet** - колоночный, сжатие, Spark/Hive
- **ORC** - колоночный, оптимизирован для Hive
- **Avro** - строковый, schema evolution, Kafka
- **JSON** - текстовый, читаемый, неэффективный
- **CSV** - простой, но без типов данных

---

## Слайд 70: Сравнение форматов

```mermaid
graph TB
    subgraph "Характеристики"
        C1[Компрессия]
        C2[Скорость чтения]
        C3[Скорость записи]
        C4[Schema Evolution]
        C5[Читаемость]
    end
    
    Parquet[Parquet<br/>★★★★★ Компрессия<br/>★★★★★ Чтение<br/>★★★☆☆ Запись]
    ORC[ORC<br/>★★★★★ Компрессия<br/>★★★★★ Чтение<br/>★★★☆☆ Запись]
    Avro[Avro<br/>★★★☆☆ Компрессия<br/>★★★☆☆ Чтение<br/>★★★★★ Запись]
    JSON[JSON<br/>★☆☆☆☆ Компрессия<br/>★★☆☆☆ Чтение<br/>★★★★☆ Запись]
    
    C1 --> Parquet & ORC
    C2 --> Parquet & ORC
    C3 --> Avro
    C4 --> Avro
    C5 --> JSON
    
    style Parquet fill:#4CAF50
    style ORC fill:#2196F3
    style Avro fill:#FF9800
    style JSON fill:#9C27B0
```

---

## Слайд 71: Резюме раздела 5

### Распределенные файловые системы

- **HDFS:** Hadoop, блоки, репликация
- **S3:** Object storage, классы хранения
- **Delta Lake:** ACID, time travel, upserts
- **Форматы:** Parquet, ORC, Avro
- **Выбор:** Зависит от паттернов доступа
- **Оптимизация:** Партиции, компрессия, формат

---

## Слайд 72: Общее резюме лекции

### Современные хранилища данных

**Реляционные БД:**
- ACID, SQL, нормализация
- OLTP системы

**Data Lakes & Warehouses:**
- DWH для BI, Lake для гибкости
- Lakehouse - лучшее из обоих

**Колоночные БД:**
- ClickHouse, BigQuery
- Оптимизация для аналитики

**NoSQL:**
- Document, Key-Value, Column, Graph
- Выбор по типу данных

**Распределенные FS:**
- HDFS, S3, Delta Lake
- Масштабируемость и надежность

---

## Слайд 73: Связи с другими лекциями

```mermaid
graph TB
    L1[Лекция 1:<br/>Архитектура систем]
    L2[Лекция 2:<br/>Сбор данных]
    L6[Лекция 6:<br/>ETL/ELT]
    L7[Лекция 7:<br/>Хранилища<br/>ТЕКУЩАЯ]
    L8[Лекция 8:<br/>Мониторинг]
    
    L1 -->|Выбор архитектуры| L7
    L2 -->|Источники данных| L7
    L6 -->|Загрузка в хранилища| L7
    L7 -->|Мониторинг качества| L8
    
    style L7 fill:#4CAF50
    style L1 fill:#e1f5ff
    style L2 fill:#e1f5ff
    style L6 fill:#e1f5ff
    style L8 fill:#fff4e1
```

---

## Слайд 74: Домашнее задание

### Практические задачи

**Задача 1: SQL практика** (3 балла)
- Создать нормализованную схему БД для интернет-магазина
- Написать 5 аналитических запросов с JOIN, GROUP BY, подзапросами

**Задача 2: Выбор хранилища** (4 балла)
- Проанализировать кейс (будет предоставлен)
- Обосновать выбор типа хранилища
- Спроектировать архитектуру

**Задача 3: Практика с NoSQL** (3 балла)
- Реализовать простое приложение с MongoDB или Redis
- Сравнить производительность с реляционной БД

**Срок сдачи:** 2 недели

---

## Слайд 75: Список литературы

### Основная литература

1. **Kleppmann, M.** "Designing Data-Intensive Applications" (2017)
2. **Kimball, R., Ross, M.** "The Data Warehouse Toolkit" (2013)
3. **Sadalage, P., Fowler, M.** "NoSQL Distilled" (2012)

### Дополнительная литература

4. **ClickHouse Documentation** - clickhouse.com/docs
5. **Google BigQuery Best Practices** - cloud.google.com/bigquery
6. **MongoDB University** - university.mongodb.com
7. **Delta Lake Documentation** - delta.io

### Онлайн ресурсы

- AWS Big Data Blog
- Google Cloud Blog
- DataEngineering.wiki

---

## Слайд 76: Вопросы и обсуждение

### Обсудим вместе

**Вопросы для дискуссии:**

1. Когда стоит выбрать NoSQL вместо SQL?
2. Data Lake vs Data Warehouse для вашего проекта?
3. Опыт работы с колоночными БД?
4. Проблемы с масштабированием данных?

**Контакты для вопросов:**
- Email: [преподаватель]
- Telegram: [канал курса]
- Консультации: [время и место]

---

## Слайд 77: Спасибо за внимание!

# Вопросы?

**Следующая лекция:**
Лекция 8: Мониторинг, тестирование и DevOps

**Подготовьтесь:**
- Установите Docker
- Зарегистрируйтесь в облачном провайдере (trial)
- Повторите основы Git

---

## Ответы на вопросы для проверки

**Вопрос 1:** B) LEFT JOIN  
**Вопрос 2:** A) Atomicity  
**Вопрос 3:** C) Raw Zone  
**Вопрос 4:** B) Читают только нужные столбцы  
**Вопрос 5:** D) Neo4j