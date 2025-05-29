from flask import Blueprint, render_template, request, flash, redirect, url_for
from app import db # Правильный импорт db из пакета app
from app.models import Course, Category, User, Review # <--- ИСПРАВЛЕНО: добавлено 'app.'
from app.tools import CoursesFilter, ImageSaver # <--- ИСПРАВЛЕНО: tools.py находится ВНУТРИ пакета app
from app.forms import ReviewForm # Этот импорт уже был правильным!
from flask_login import current_user, login_required

bp = Blueprint('courses', __name__, url_prefix='/courses')

COURSE_PARAMS = [
    'author_id', 'name', 'category_id', 'short_desc', 'full_desc'
]

def params():
    return { p: request.form.get(p) for p in COURSE_PARAMS }

def search_params():
    return {
        'name': request.args.get('name'),
        'category_ids': [x for x in request.args.getlist('category_ids') if x],
    }

@bp.route('/')
def index():
    courses = CoursesFilter(**search_params()).perform()
    pagination = db.paginate(courses)
    courses = pagination.items
    categories = db.session.execute(db.select(Category)).scalars()
    return render_template('courses/index.html',
                           courses=courses,
                           categories=categories,
                           pagination=pagination,
                           search_params=search_params())

@bp.route('/new')
@login_required
def new():
    categories = db.session.execute(db.select(Category)).scalars()
    users = db.session.execute(db.select(User)).scalars()
    return render_template('courses/new.html',
                           categories=categories,
                           users=users)

@bp.route('/create', methods=['POST'])
@login_required
def create():

    f = request.files.get('background_img')
    img = None
    if f and f.filename:
        img = ImageSaver(f).save()

    course = Course(**params(), background_image_id=img.id if img else None)
    db.session.add(course)
    db.session.commit()

    flash(f'Курс {course.name} был успешно добавлен!', 'success')

    return redirect(url_for('courses.index'))

@bp.route('/<int:course_id>', methods=['GET', 'POST'])
def show(course_id):
    course = db.get_or_404(Course, course_id)

    recent_reviews = Review.query.filter_by(course_id=course.id) \
                                 .order_by(Review.created_at.desc()) \
                                 .limit(5) \
                                 .all()

    user_review = None
    form = None
    if current_user.is_authenticated:
        user_review = Review.query.filter_by(course_id=course.id, user_id=current_user.id).first()

        if not user_review:
            form = ReviewForm()
            if form.validate_on_submit():
                new_review = Review(
                    rating=form.rating.data,
                    text=form.text.data,
                    course_id=course.id,
                    user_id=current_user.id
                )
                db.session.add(new_review)

                course.rating_sum += new_review.rating
                course.rating_num += 1

                db.session.commit()
                flash('Ваш отзыв успешно добавлен!', 'success')
                return redirect(url_for('courses.show', course_id=course.id))

    return render_template('courses/show.html',
                           course=course,
                           recent_reviews=recent_reviews,
                           form=form,
                           user_review=user_review
                           )

@bp.route('/<int:course_id>/reviews', methods=['GET', 'POST'])
def course_reviews(course_id):
    course = db.get_or_404(Course, course_id)

    sort_order = request.args.get('sort', 'newest')
    page = request.args.get('page', 1, type=int)

    reviews_query = Review.query.filter_by(course_id=course.id) \
                                .options(db.joinedload(Review.user))

    if sort_order == 'newest':
        reviews_query = reviews_query.order_by(Review.created_at.desc())
    elif sort_order == 'positive':
        reviews_query = reviews_query.order_by(Review.rating.desc(), Review.created_at.desc())
    elif sort_order == 'negative':
        reviews_query = reviews_query.order_by(Review.rating.asc(), Review.created_at.desc())

    per_page = 5
    reviews_pagination = db.paginate(reviews_query, page=page, per_page=per_page, error_out=False)
    
    user_review = None
    form = None
    if current_user.is_authenticated:
        user_review = Review.query.filter_by(course_id=course.id, user_id=current_user.id).first()

        if not user_review:
            form = ReviewForm()
            if form.validate_on_submit():
                new_review = Review(
                    rating=form.rating.data,
                    text=form.text.data,
                    course_id=course.id,
                    user_id=current_user.id
                )
                db.session.add(new_review)
                
                course.rating_sum += new_review.rating
                course.rating_num += 1
                
                db.session.commit()
                flash('Ваш отзыв успешно добавлен!', 'success')
                return redirect(url_for('courses.course_reviews', course_id=course.id, page=page, sort=sort_order))

    return render_template('courses/reviews.html',
                           course=course,
                           reviews_pagination=reviews_pagination,
                           sort_order=sort_order,
                           form=form,
                           user_review=user_review
                           )