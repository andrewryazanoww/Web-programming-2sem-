# app/tools.py
import hashlib
import uuid
import os
from werkzeug.utils import secure_filename
from flask import current_app
from .extensions import db
from .models import Image, Equipment, Category, User # Убедитесь, что все модели импортированы

class ImageSaver:
    def __init__(self, file_storage, upload_folder_config_key='UPLOAD_FOLDER_EQUIPMENT'):
        if not file_storage or not file_storage.filename:
            current_app.logger.info("ImageSaver: файл не предоставлен или имя файла пустое.")
            self.file = None; self.md5_hash = None; self.image_model_instance = None
            return
        self.file = file_storage
        self.upload_folder = current_app.config.get(upload_folder_config_key)
        if not self.upload_folder:
            current_app.logger.error(f"Ключ конфигурации '{upload_folder_config_key}' не найден.")
            raise ValueError(f"Конфигурация папки для загрузки '{upload_folder_config_key}' отсутствует.")
        self.md5_hash = None; self.image_model_instance = None

    def _calculate_md5_hash(self):
        if not self.file: return None
        file_content = self.file.read()
        if not file_content: self.file.seek(0); return None
        self.md5_hash = hashlib.md5(file_content).hexdigest()
        self.file.seek(0)
        return self.md5_hash

    def _find_existing_image_by_md5(self):
        if not self.md5_hash:
            if self._calculate_md5_hash() is None: return None
        return db.session.execute(db.select(Image).filter_by(md5_hash=self.md5_hash)).scalar_one_or_none()

    def save(self):
        if not self.file: return None
        self.image_model_instance = self._find_existing_image_by_md5()
        if self.image_model_instance: return self.image_model_instance
        if not self.md5_hash: return None

        original_file_name = secure_filename(self.file.filename)
        image_id = str(uuid.uuid4())
        self.image_model_instance = Image(id=image_id, file_name=original_file_name, mime_type=self.file.mimetype, md5_hash=self.md5_hash)
        if not os.path.exists(self.upload_folder):
            try: os.makedirs(self.upload_folder)
            except OSError as e: current_app.logger.error(f"Не удалось создать папку {self.upload_folder}: {e}"); return None
        save_path = os.path.join(self.upload_folder, self.image_model_instance.storage_filename)
        try: self.file.save(save_path)
        except Exception as e: current_app.logger.error(f"Не удалось сохранить файл {save_path}: {e}"); return None
        db.session.add(self.image_model_instance)
        return self.image_model_instance

class EquipmentFilter:
    def __init__(self, name_filter=None, category_id=None, status=None, purchase_date_from=None, purchase_date_to=None, sort_by='purchase_date', sort_direction='desc'):
        self.name_filter = name_filter
        self.category_id = category_id
        self.status = status
        self.purchase_date_from = purchase_date_from # Ожидается объект date
        self.purchase_date_to = purchase_date_to     # Ожидается объект date
        # Допустимые поля для сортировки
        valid_sort_fields = {
            'name': Equipment.name,
            'inventory_number': Equipment.inventory_number,
            'purchase_date': Equipment.purchase_date,
            'status': Equipment.status,
            'category_name': Category.name # Сортировка по имени категории
        }
        self.sort_by_column = valid_sort_fields.get(sort_by, Equipment.purchase_date) # Поле SQLAlchemy для сортировки
        self.sort_direction = sort_direction if sort_direction in ['asc', 'desc'] else 'desc'
        # Начинаем с базового запроса, присоединяем Category для возможности сортировки по имени категории
        self.query = db.select(Equipment).join(Category, Equipment.category_id == Category.id, isouter=True)

    def perform(self):
        if self.name_filter: self.query = self.query.filter(Equipment.name.ilike(f'%{self.name_filter}%'))
        if self.category_id and self.category_id > 0: self.query = self.query.filter(Equipment.category_id == self.category_id)
        if self.status: self.query = self.query.filter(Equipment.status == self.status)
        if self.purchase_date_from: self.query = self.query.filter(Equipment.purchase_date >= self.purchase_date_from)
        if self.purchase_date_to: self.query = self.query.filter(Equipment.purchase_date <= self.purchase_date_to)
        
        if self.sort_direction == 'asc':
            self.query = self.query.order_by(self.sort_by_column.asc())
        else:
            self.query = self.query.order_by(self.sort_by_column.desc())
        # Дополнительная сортировка по ID для стабильности, если основные значения сортировки одинаковы
        self.query = self.query.order_by(Equipment.id.desc() if self.sort_direction == 'desc' else Equipment.id.asc())
        return self.query