// app/static/js/main.js
'use strict';

// Пример функции для инициализации всплывающих подсказок Bootstrap (если используются)
function initializeBootstrapTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Пример функции для модального окна (адаптируйте под ваши нужды)
// Этот код уже был в вашем index.html для оборудования, но можно вынести в main.js
// и вызывать для разных модальных окон, передавая параметры.
function setupDeleteModal(modalId, nameElementId, formId, urlBase) {
    const deleteModal = document.getElementById(modalId);
    if (deleteModal) {
        deleteModal.addEventListener('show.bs.modal', event => {
            const button = event.relatedTarget;
            const itemId = button.getAttribute('data-item-id'); // Общее имя атрибута
            const itemName = button.getAttribute('data-item-name');

            const modalItemNameElement = deleteModal.querySelector('#' + nameElementId);
            const deleteForm = deleteModal.querySelector('#' + formId);

            if (modalItemNameElement) {
                modalItemNameElement.textContent = itemName;
            }
            if (deleteForm) {
                deleteForm.action = `${urlBase}/${itemId}/delete`; // Формируем URL
            }
        });
    }
}


window.addEventListener('DOMContentLoaded', (event) => {
    console.log('DOM fully loaded and parsed');
    initializeBootstrapTooltips();

    // Вызываем настройку для модального окна удаления оборудования, если оно есть на странице
    // (Предполагается, что ID модального окна 'deleteEquipmentModal',
    // элемента для имени 'deleteEquipmentName', формы 'deleteEquipmentForm',
    // и базовый URL для удаления '/equipment')
    if (document.getElementById('deleteEquipmentModal')) {
        setupDeleteModal('deleteEquipmentModal', 'deleteEquipmentName', 'deleteEquipmentForm', '/equipment');
    }

    // Ваш JS для превью изображения (если он был в отдельном файле, можно добавить сюда)
    // Пример imagePreviewHandler из вашего задания
    function imagePreviewHandler(event) {
        if (event.target.files && event.target.files[0]) {
            let reader = new FileReader();
            let previewContainer = event.target.closest('.col-md-6').querySelector('.background-preview');
            if (!previewContainer) return;

            let img = previewContainer.querySelector('img');
            let label = previewContainer.querySelector('label');

            reader.onload = function (e) {
                if (img) {
                    img.src = e.target.result;
                    img.classList.remove('d-none');
                }
                if (label) {
                    label.classList.add('d-none');
                }
            }
            reader.readAsDataURL(event.target.files[0]);
        }
    }

    let background_img_field = document.getElementById('background_img'); // ID из формы new.html
    if (background_img_field) {
        background_img_field.onchange = imagePreviewHandler;
    }

    // Код для кликабельных строк в списке курсов из вашего main.js
    for (let course_elm of document.querySelectorAll('.courses-list .row[data-url]')) {
        course_elm.onclick = function(event) {
            // Предотвращаем переход, если клик был по кнопке или ссылке внутри строки
            if (event.target.closest('a, button')) {
                return;
            }
            window.location = this.dataset.url;
        };
    }

});