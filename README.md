# nko_nzhkc

### Makefile
Make — одна из базовых утилит Юникса, есть на каждой юниксовой машине.
Чтобы проект на Джанге развернуть на новом сервере, нужно выполнить команд пять-десять.
Утилита Make вполне гибкая и может отследить точно, что нужно пересобрать и при этом не пересобирать лишнее.

<details>
    <summary><b>Make на Windows. Ссылка на статью</b></summary>

```shell
https://thelinuxcode.com/run-makefile-windows/
```
</details>

### Pre-commit
Для минимизации трудностей во время разработки и поддержании высокого качества кода в разработке мы используем `pre-commit`. Данный фреймворк позволяет проверить код на соответствие `PEP8`, защитить ветки main и develop от непреднамеренного коммита, проверить корректность импортов и наличие trailing spaces.
`Pre-commit` конфигурируется с помощью специального файл `.pre-commit-config.yaml`. Для использования фреймворка его необходимо установить, выполнив команду из активированного виртуального окружения:

```bash
(venv)$ pip install pre-commit
```
или 

```bash
(venv)$ pip install -r requirements-dev.txt
```
Для принудительной проверки всех файлов можно выполнить команду:
```bash
(venv)$ pre-commit run --all-files
```
При первом запуске будут скачаны и установлены все необходимые хуки, указанные в конфигурационном файле.

Для автоматической проверки всех файлов необходимо инициализировать фреймворк командой:
```bash
(venv)$ pre-commit install
```

### Celery
Celery включен в индекс пакетов Python (PyPI), поэтому его можно установить с помощью стандартных инструментов Python,
таких как pip:

```bash
(venv)$ pip install celery
```

В проекте реализовано логирование задач Celery в отдельный файл celery.log, на уровне INFO.

### RabbitMQ 
Является полнофункционалным, стабильным и надежным и простым в установке. Это отличный выбор для производственной
среды. Подробная информаци об использования RabbitMQ с Celery

<details>
    <summary><b>Использование RabbitMQ.</b></summary>

```shell
https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/rabbitmq.html#broker-rabbitmq
```
</details>

Если вы используете Linux, установите RabbitMQ, выполнив эту команду

```bash
$ sudo apt-get install rabbitmq-server
```

Или, если вы хотите запустить его в Docker, выполните следующее:

```bash
$ docker run -d -p 5672:5672 rabbitmq
```

Когда команда завершится, брокер уже будет работать в фоновом режиме и готов переместить для вас сообщения: 
.Starting rabbitmq-server: SUCCESS
Вы можете зайти на этот сайт и найти аналогичные простые инструкции по установке для других платформ,
включая Microsoft Windows:

<details>
    <summary><b>Установка RabbitMQ</b></summary>

```shell
http://www.rabbitmq.com/download.html
```
</details>

### Cloudpayment
Интернет-эйквайринг, позволяющий получать платежи онлайн с помощью банковской карты или различными методами  быстрой
оплаты.

<details>
    <summary><b>Подробнее о сервисе</b></summary>

```shell
https://cloudpayments.ru/integration
```
</details>

Интеграция с Cloudpayments в проекте включает в себя:
- Настройка API-ключа. Ключ выдается платформой при регистрации, добавлен в настройки проекта.
- Обработка платежей осуществляется засчет ответов API. При успешном платеже, а также при неуспешной попытке платежа 
создается соответствуюшая запись в базе данных проекта.
- Взаимодействие осуществляется посредством сервиса Stripe, который агрегирует уже созданные платежи. Платежи проходят 
через сервис Cloudpayments на стороне заказчика.
- Реализована возможность проверки подключения к API Cloudpayments с помощью тест-кейса Django.

### Stripe
Сервис для приёма и обработки электронных платежей. 
В проекте задействован как хранилище всего массива информации о платежах от двух эквайрингов.

<details>
    <summary><b>Подробнее о сервисе</b></summary>

```shell
https://docs.stripe.com/api
```
</details>

Как реализовано: 

- при создании объекта модели Cloudpayment и/или Mixplat срабатывает сигнал, 
который запускает метод, создающий "Платежное намерение" в терминологии Stripe
- в платежное намерение попадают не все данные о платеже, только обозначенные нами
- чтобы клиент смог использовать функционал, необходима регистрация в Stripe и получение ключей доступа
- все платежные намерения хранятся на стороне Stripe, при желании, их можно получить по API:

```request
GET /v1/payment_intents
```

```request
stripe.PaymentIntent.list(limit=3)
```
<details>
    <summary><b>Подробнее можно изучить здесь</b></summary>

```shell
https://docs.stripe.com/api/payment_intents/list
```
</details>


### Письма о статусе платежа

Реализованы с помощью сигналов Django. 
При создании объекта модели Cloudpayment и/или Mixplat срабатывает сигнал, 
который запускает проверку статуса платежа из данных от эквайринга.

- если статус "rejected" - платеж отклонен, пользователю уходит письмо через Unisender
- если не сработали маркеры "created" и "rejected" - платеж обновлен, пользователю уходит письмо через Unisender
- В ином случае - платеж прошел, пользователю уходит письмо через Unisender.