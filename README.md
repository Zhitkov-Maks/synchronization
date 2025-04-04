# SYNCHRONIZATION SERVICE

***

Сервис для синхронизации файлов, в папке на компьютере с облачным хранилищем(на данный момент с 
яндекс диском).

### Основной функционал

- Приложение с заданной периодичностью изучает файлы в отслеживаемой папке.
- При появлении нового локального файла он загружается в облачное хранилище.
- При изменении локального файла его новая версия загружается в облачное хранилище.
- При удалении локального файла он удаляется из облачного хранилища.
- Можно создавать любое количество вложенных папок и загружать туда файлы.

### Используемый стек.

- python3.13
- aiohttp

### Запуск программы на линукс(ubuntu)

- Создаем виртуальное окружение. ```python3 -m venv .venv```
- Активируем его ```source .venv/bin/activate```
- Устанавливаем зависимости ```pip install -r requirements txt```
- Создаем файл .env и записываем в него нужные данные по примеру как в файле .env.template
- Запускаем программу python3 main.py

В данном случае программа будет работать пока открыт терминал. 

Пример запуска в фоне на ubuntu:

```chmod +x main.py``` - добавим права файлу, чтобы разрешить выполнение.

```nohup python3 main.py 2>&1 >/dev/null &``` -  запускаем программу.

Теперь программа должна работать в фоновом режиме.

Чтобы остановить, нужно узнать PID ```ps ax | grep main.py``` - kill PID.

### Замеченные возможные ошибки.

Заметил что если файл сохранен с использованием символов +, то в облаке он будет сохранен с пробелами вместо символа +,
и вследствии этого будет постоянное недопонимание между облаком и пк, и файл будет то удалятся, то загружаться с 
показом ошибки "Ресурс уже существует". Поэтому следует избегать в названии файлов символов +.

#### Очень медленная загрузка некоторых типов файлов на Яндекс.Диск
REST API Яндекс.Диск ограничивает скорость загрузки файлов на Диск до 128 KiB/s для определенных MIME типов файлов. 
Если быть точнее, троттлинг осуществляется в зависимости от значения media_type (см. yadisk.Client.get_meta). 
С удя по всему ограничение скорости действует на 3 типа файлов (media type):

- data (.db, .dat, etc.)
- compressed (.zip, .gz, .tgz, .rar, .etc)
- video (.3gp, .mp4, .avi, etc.)

Ограничение скорости предопределяется в момент получения ссылки для загрузки файла на диск 
(см. yadisk.Client.get_upload_link). Содержимое загружаемого файла не имеет значения. Причина, по которой 
эта проблема не наблюдается при попытке загрузить файл через официальный сайт, 
заключается в том, что ограничение скорости не применяется для внутренних сервисов 
(сайт Яндекс.Диска использует промежуточный внутренний API для получения ссылок).
Хотя и не понятно, в чем смысл такого ограничения, это точно не баг.

Единственный известный способ обхода данной проблемы - это загрузка файлов с измененным расширением 
(или без расширения). Например, если вы хотите загрузить на Диск файл «my_database.db», 
вы можете изначально загрузить его под именем «my_database.some_other_extension» 
и после загрузки переименовать обратно в «my_database.db». 
У такого подхода есть очевидные недостатки, но по крайней мере он работает.

## Настройка Python-скрипта как systemd сервиса в Manjaro/Arch Linux

***

### Описание
Данное руководство объясняет, как настроить автоматический запуск Python-скрипта как systemd 
сервиса с использованием виртуального окружения.

#### Предварительные требования

- Manjaro/Arch Linux(Вообще должно работать и на других Linux).
- Python 3.13
- Пользователь user(замените на ваше имя пользователя).
- Установленный systemd

#### Настройка 

1. Настройка прав.

```commandline
sudo chown -R user:user /home/user/development/synchronization
chmod +x /home/user/development/synchronization/main.py
```

2. Создание сервисного файла.

```commandline
sudo nano /etc/systemd/system/my_script.service
```

```commandline
[Unit]
Description=My Python Script
After=network.target

[Service]
Type=simple
User=user
Group=user
WorkingDirectory=/home/user/development/synchronization
ExecStart=/bin/bash -c 'source /home/user/development/synchronization/.venv/bin/activate && exec python /home/user/development/synchronization/main.py'
Restart=on-failure
RestartSec=30s
Environment="PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/home/user/development/synchronization/.venv/bin"

[Install]
WantedBy=multi-user.target
```

3. Активация сервиса.

```commandline
sudo systemctl daemon-reload
sudo systemctl enable my_script.service
sudo systemctl start my_script.service
```

#### Управление сервисом

- Проверить статус
```commandline
sudo systemctl status my_script.service
```
- Запустить сервис
```commandline
sudo systemctl start my_script.service
```
- Остановить сервис
```commandline
sudo systemctl stop my_script.service
```
- Перезапустить сервис
```commandline
sudo systemctl restart my_script.service
```

- Просмотр логов
```commandline
journalctl -u my_script.service -f
```

#### Устранение неполадок

##### Если сервис не запускается
 - Проверьте пути в сервисном файле
 - Убедитесь, что виртуальное окружение активируется:
```commandline
sudo -u user /bin/bash -c 'source /home/user/development/synchronization/.venv/bin/activate && python /home/user/development/synchronization/main.py'
```
- Проверьте права:
```commandline
ls -la /home/user/development/synchronization/
```

#### Ошибка 217/USER
- Убедитесь, что пользователь user существует:
```commandline
id user
```
- Если нет, создайте его:
```commandline
sudo useradd -m -s /bin/bash user
```
