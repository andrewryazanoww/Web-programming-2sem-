# app/tools.py
import hashlib
import uuid
import os
from werkzeug.utils import secure_filename
from flask import current_app
from .extensions import db
from .models import Image, Equipment # Убрали Course, добавили Equipment для EquipmentFilter (если он будет)

class ImageSaver:
    def __init__(self, file_storage, upload_folder_config_key='UPLOAD_FOLDER_EQUIPMENT'):
        if not file_storage or not file_storage.filename:
            raise ValueError("Необходимо предоставить корректный объект FileStorage (файл не выбран или имя файла пустое).")
        self.file = file_storage
        self.upload_folder = current_app.config.get(upload_folder_config_key)
        if not self.upload_folder:
            current_app.logger.error(f"Ключ конфигурации '{upload_folder_config_key}' для папки загрузки не найден или пуст в app.config.")
            raise ValueError(f"Ключ конфигурации '{upload_folder_config_key}' для папки загрузки не найден или пуст.")
        self.md5_hash = None
        self.image_model_instance = None

    def _calculate_md5_hash(self):
        file_content = self.file.read()
        if not file_content:
             self.file.seek(0)
             raise ValueError("Попытка загрузить пустой файл (содержимое не читается).")
        self.md5_hash = hashlib.md5(file_content).hexdigest()
        self.file.seek(0)

    def _find_existing_image_by_md5(self):
        if not self.md5_hash:
            self._calculate_md5_hash()
        return db.session.execute(
            db.select(Image).filter_by(md5_hash=self.md5_hash)
        ).scalar_one_or_none()

    def save(self):
        try:
            self.image_model_instance = self._find_existing_image_by_md5()
            if self.image_model_instance:
                current_app.logger.info(f"Изображение с MD5 {self.md5_hash} уже существует (ID: {self.image_model_instance.id}). Используется существующее.")
                return self.image_model_instance
        except ValueError as e:
            current_app.logger.error(f"Ошибка при вычислении MD5 или поиске изображения: {e}")
            raise

        original_file_name = secure_filename(self.file.filename)
        image_id = str(uuid.uuid4())
        self.image_model_instance = Image(
            id=image_id,
            file_name=original_file_name,
            mime_type=self.file.mimetype,
            md5_hash=self.md5_hash
        )
        if not os.path.exists(self.upload_folder):
            try:
                os.makedirs(self.upload_folder)
                current_app.logger.info(f"Создана папка для загрузки изображений: {self.upload_folder}")
            except OSError as e:
                current_app.logger.error(f"Критическая ошибка: Не удалось создать папку {self.upload_folder}: {e}")
                raise
        save_path = os.path.join(self.upload_folder, self.image_model_instance.storage_filename)
        try:
            self.file.save(save_path)
            current_app.logger.info(f"Файл изображения сохранен как: {save_path}")
        except Exception as e:
            current_app.logger.error(f"Критическая ошибка: Не удалось сохранить файл изображения {save_path}: {e}")
            raise
        db.session.add(self.image_model_instance)
        return self.image_model_instance

# Если EquipmentFilter не используется в этом проекте, его можно полностью удалить.
# Если используется, он должен работать с моделью Equipment, а не Course.
# class EquipmentFilter:
#     def __init__(self, name=None, category_id=None, status=None, purchase_date_from=None, purchase_date_to=None):
#         self.name = name
#         self.category_id = category_id
#         self.status = status
#         self.purchase_date_from = purchase_date_from
#         self.purchase_date_to = purchase_date_to
#         self.query = db.select(Equipment) # Используем модель Equipment

#     def perform(self):
#         if self.name:
#             self.query = self.query.filter(Equipment.name.ilike(f'%{self.name}%'))
#         if self.category_id:
#             try:
#                 cat_id_int = int(self.category_id)
#                 if cat_id_int > 0:
#                     self.query = self.query.filter(Equipment.category_id == cat_id_int)
#             except (ValueError, TypeError):
#                 pass
#         if self.status:
#             self.query = self.query.filter(Equipment.status == self.status)
#         if self.purchase_date_from:
#             self.query = self.query.filter(Equipment.purchase_date >= self.purchase_date_from)
#         if self.purchase_date_to:
#             self.query = self.query.filter(Equipment.purchase_date <= self.purchase_date_to)
        
#         return self.query.order_by(Equipment.purchase_date.desc())