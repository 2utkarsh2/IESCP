import os
from functools import wraps
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, session, make_response
from flask_login import current_user
from app import db, User, Campaign ,AdRequest,Profile,Rating
from werkzeug.utils import secure_filename
from app import app
import urllib.request
from sqlalchemy import and_

@app.context_processor
def inject_user():
    user_id = session.get('user_id')
    user = User.query.get(user_id) if user_id else None
    return {'user': user}

# Login required decorator
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('You need to be logged in to access that page.', 'danger')
            return redirect(url_for('login'))
        return func(*args, **kwargs)
    return wrapper

def check_flagged_user(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = User.query.get(session.get('user_id'))
        if user and user.flag:
            # Log out the user by clearing the session
            session.clear()
            flash("You have been logged out because you were flagged by the admin.", 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required

def index():
    return render_template('layout.html')

@app.route('/profile', methods=['GET', 'POST'])
@login_required
@check_flagged_user

def profile():
    user = User.query.get(session['user_id'])    
    if user.role == 'influencer':
        sent_requests = AdRequest.query.filter_by(sender_id=user.id).all()
        received_requests = AdRequest.query.filter_by(receiver_id=user.id).all()

        # Calculate average rating
        ratings = Rating.query.filter_by(ratee_id=user.id).all()
        if ratings:
            avg_rating = round(sum(r.rating for r in ratings) / len(ratings), 2)
        else:
            avg_rating = None

        # Calculate total payment from both sent and received completed requests
        sent_completed_requests = AdRequest.query.filter_by(sender_id=user.id, status='Payment Complete').all()
        received_completed_requests = AdRequest.query.filter_by(receiver_id=user.id, status='Payment Complete').all()
        total_payment = sum(req.payment for req in sent_completed_requests + received_completed_requests)

        return render_template('profile.html', user=user, sent_requests=sent_requests, received_requests=received_requests, avg_rating=avg_rating, total_payment=total_payment)
    
    elif user.role == 'sponsor':
        sent_requests = AdRequest.query.filter_by(sender_id=user.id).all()
        received_requests = AdRequest.query.filter_by(receiver_id=user.id).all()
        
        return render_template('sponsor.html', user=user, sent_requests=sent_requests, received_requests=received_requests)
    
    elif user.role == 'admin':
        users = User.query.filter((User.role == 'sponsor') | (User.role == 'influencer')).all()
        total_users = User.query.count()
        total_sponsors = User.query.filter_by(role='sponsor').count()
        total_influencers = User.query.filter_by(role='influencer').count()

        total_adrequests = AdRequest.query.count()
        total_campaigns = Campaign.query.count()
        campaigns = Campaign.query.all()
        campaign_titles = [campaign.title for campaign in campaigns]
        campaign_budgets = [campaign.budget for campaign in campaigns]

        influencers = User.query.filter_by(role='influencer').all()
        platform_data = {'youtube': 0, 'instagram': 0, 'x': 0, 'facebook': 0, 'linkedin':0}
        niche_data = {}

        for influencer in influencers:
            platform_data[influencer.socialnet] += 1

        for user in users:
            if user.niche in niche_data:
                niche_data[user.niche] += 1
            else:
                niche_data[user.niche] = 1

        platform_labels = list(platform_data.keys())
        platform_data_values = list(platform_data.values())

        niche_labels = list(niche_data.keys())
        niche_data_values = list(niche_data.values())

        return render_template('admin_panel.html',
                                total_users=total_users,
                                total_sponsors=total_sponsors,
                                total_influencers=total_influencers,
                                total_campaigns = total_campaigns,
                                total_adrequests = total_adrequests,
                                campaign_titles=campaign_titles,
                                campaign_budgets=campaign_budgets,
                                platform_labels=platform_labels,
                                platform_data=platform_data_values,
                                niche_labels=niche_labels,
                                niche_data=niche_data_values)

@app.route('/admin_search/<search_type>/', methods=['GET'])
@login_required

def admin_search(search_type):


    query = request.args.get('query', '')
    filter_by = request.args.get('filter', '')

    if search_type == 'sponsors':
        items = User.query.filter_by(role='sponsor')
        if query:
            if filter_by == 'sponsor_name':
                items = items.filter(User.name.ilike(f'%{query}%'))
            elif filter_by == 'sponsor_niche':
                items = items.filter(User.niche.ilike(f'%{query}%'))
    elif search_type == 'influencers':
        items = User.query.filter_by(role='influencer')
        if query:
            if filter_by == 'influencer_name':
                items = items.filter(User.name.ilike(f'%{query}%'))
            elif filter_by == 'influencer_niche':
                items = items.filter(User.niche.ilike(f'%{query}%'))
            elif filter_by == 'influencer_social':
                items = items.filter(User.socialnet.ilike(f'%{query}%'))
    elif search_type == 'campaigns':
        items = Campaign.query
        if query:
            if filter_by == 'campaign_title':
                items = items.filter(Campaign.title.ilike(f'%{query}%'))
            elif filter_by == 'campaign_niche':
                items = Campaign.query.join(User).filter(
                    and_(
                        Campaign.visibility == 'Public' or Campaign.visibility == 'Private',
                        User.role == 'sponsor',
                        User.niche.ilike(f"%{query}%")
                    ))
            elif filter_by == 'campaign_budget':
                items = items.filter(Campaign.budget >= float(query))

    items = items.all()

    return render_template('admin_search.html', search_type=search_type, items=items)


@app.route('/view_ad_request/<int:request_id>')
@check_flagged_user
@login_required
def view_ad_request(request_id):
    ad_request = AdRequest.query.get_or_404(request_id)
    return render_template('view_ad_request.html', ad_request=ad_request)

@app.route('/view_campaign/<int:campaign_id>')
@check_flagged_user
@login_required
def view_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    ad_requests = AdRequest.query.filter_by(campaign_id=campaign.id).all()
    return render_template('view_campaign.html', campaign=campaign, ad_requests=ad_requests)

@app.route('/handle_request/<int:request_id>', methods=['POST'])
@login_required
def handle_request(request_id):
    ad_request = AdRequest.query.get_or_404(request_id)
    action = request.form.get('action')

    if action == 'accept':
        ad_request.status = 'Accepted'
        flash('Ad request confirmed successfully!', 'success')

    elif action == 'reject':
        ad_request.status = 'Rejected'
        flash('Ad request rejected.', 'danger')

    elif action == 'completed':
        ad_request.status = 'Completed'
        flash('Campaign completed successfully.', 'success')

    db.session.commit()
    return redirect(url_for('profile'))

@app.route('/pay_request/<int:request_id>', methods=['GET', 'POST'])
@login_required
@check_flagged_user
def pay_request(request_id):
    ad_request = AdRequest.query.get_or_404(request_id)
    user = User.query.get(session['user_id'])

    # Ensure only sponsors can pay and the ad request is completed
    if user.role != 'sponsor' or ad_request.status != 'Completed':
        flash('You do not have permission to pay for this request.', 'danger')
        return redirect(url_for('profile'))

    if request.method == 'POST':
        rating = request.form.get('rating')
        review = request.form.get('review')
        payment = request.form.get('payment')

        # Validate the rating
        if int(rating) < 0 or int(rating) > 5:
            flash('Rating must be between 0 and 5.', 'danger')
            return render_template('pay.html', request=ad_request)

        # Determine the ratee (influencer)
        ratee_id = ad_request.receiver_id if ad_request.receiver.role == 'influencer' else ad_request.sender_id

        # Create a new Rating entry
        new_rating = Rating(
            transaction_id=ad_request.id,
            rater_id=user.id,
            ratee_id=ratee_id,
            rating=rating,
            review=review,
            date=datetime.utcnow()
        )
        db.session.add(new_rating)

        # Update ad request status
        ad_request.status = 'Payment Complete'
        db.session.commit()

        flash('Payment successful and rating submitted.', 'success')
        return redirect(url_for('profile'))

    return render_template('pay.html', request=ad_request)




@app.route('/edit_profile', methods=['POST', 'GET'])
@login_required
@check_flagged_user
def edit_profile():
    user = User.query.get(session['user_id'])

    if not user.profile:
        user.profile = Profile(user_id=user.id)
        db.session.add(user.profile)
        db.session.commit()

    if request.method == 'POST':
        # Get the form data
        new_username = request.form.get('username')
        new_email = request.form.get('email')
        new_mobile = request.form.get('mobile')
        new_name = request.form.get('name')
        new_reach = request.form.get('reach')
        new_bio = request.form.get('bio')

        # Check if the username already exists
        existing_user = User.query.filter(User.username == new_username, User.id != user.id).first()
        if existing_user:
            flash('Username already exists. Please choose a different one.', 'danger')
            return redirect(url_for('edit_profile'))

        # Check if the email already exists
        existing_email = User.query.filter(User.email == new_email, User.id != user.id).first()
        if existing_email:
            flash('Email already exists. Please choose a different one.', 'danger')
            return redirect(url_for('edit_profile'))

        # Check if the phone number already exists
        existing_mobile = Profile.query.filter(Profile.mobile == new_mobile, Profile.user_id != user.id).first()
        if existing_mobile:
            flash('Phone number already exists. Please choose a different one.', 'danger')
            return redirect(url_for('edit_profile'))

        # If validation passes, update the user's profile
        user.username = new_username
        user.name = new_name
        user.email = new_email
        user.profile.mobile = new_mobile
        user.profile.reach = new_reach
        user.profile.bio = new_bio

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('profile'))

    return render_template('edit_profile.html', user=user)


@app.route('/status/<int:request_id>', methods=['POST'])
@login_required
def delete_request(request_id):
    ad_request = AdRequest.query.get_or_404(request_id)
    if ad_request.sender_id == session['user_id'] or ad_request.receiver_id == session['user_id']:
        db.session.delete(ad_request)
        db.session.commit()
        flash('Ad request deleted successfully!', 'success')
    else:
        flash('You do not have permission to delete this ad request.', 'danger')
    return redirect(url_for('profile'))


@app.route('/campaigns', methods=['GET', 'POST'])
@check_flagged_user
@login_required
def campaigns():
    # Query campaigns by the logged-in user's ID
    user = User.query.get(session['user_id'])
    campaigns = Campaign.query.filter_by(user_id=user.id).all()
    return render_template('campaigns.html', campaigns=campaigns)


@app.route('/add_campaign', methods=['POST'])
@check_flagged_user
@login_required
def add_campaign():
    title = request.form.get('title')
    budget = request.form.get('budget')
    description = request.form.get('description')
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')
    goals = request.form.get('goals')
    visibility = request.form.get('visibility')
    
    # Convert date strings to datetime objects
    start_date = datetime.strptime(start_date, '%Y-%m-%d')
    end_date = datetime.strptime(end_date, '%Y-%m-%d')

    new_campaign = Campaign(
        title=title,
        budget=budget,
        description=description,
        start_date=start_date,
        end_date=end_date,
        visibility=visibility,
        goals=goals,
        user_id=session['user_id']
    )
    db.session.add(new_campaign)
    db.session.commit()
    
    flash('Campaign added successfully.', 'success')
    return redirect(url_for('campaigns'))  # Redirect to the campaigns page



@app.route('/ad_request/<int:campaign_id>', methods=['GET', 'POST'])
@check_flagged_user
@login_required
def ad_request(campaign_id):
    user = User.query.get(session['user_id'])
    campaign = Campaign.query.get_or_404(campaign_id)

    if request.method == 'POST':
        message = request.form.get('message')
        payment = request.form.get('payment')
        requirements = request.form.get('requirements')
        receiver_id = request.form.get('receiver_id')

        new_ad_request = AdRequest(
            campaign_id=campaign_id,
            receiver_id=receiver_id,
            sender_id=user.id,
            requirements=requirements,
            message=message,
            payment=payment,
            status='Pending'
        )

        db.session.add(new_ad_request)
        db.session.commit()
        flash('Ad request sent successfully!', 'success')
        return redirect(url_for('ad_request', campaign_id=campaign_id))

    if user.role == 'sponsor':
        # Get the list of influencers
        if campaign.visibility == 'Public':
            influencers = User.query.filter_by(role='influencer').all()
        else:
            influencers = User.query.filter_by(role='influencer', niche=user.niche).all()
        # Get the list of campaigns for the sponsor
        campaigns = Campaign.query.filter_by(user_id=user.id).all()
        if not campaigns:
            flash('Please create a campaign first.', 'danger')
            return redirect(url_for('create_campaign'))
    elif user.role == 'influencer':
        # Get the list of sponsors
        sponsors = User.query.filter_by(role='sponsor').all()

    return render_template('ad_request.html', campaign=campaign, user=user,influencers = influencers, campaigns=campaigns)

@app.route('/search', methods=['GET','POST'])
@check_flagged_user
@login_required
def search():

    user = User.query.get(session['user_id'])
    query = request.args.get('query', '')
    filter_type = request.args.get('filter', 'campaign_title')  # default to campaign_title if not specified
    
    if user.role == 'influencer':
        if filter_type:
            if filter_type == 'campaign_title':
                public_campaigns = Campaign.query.filter(
                    and_(
                        Campaign.visibility == 'Public',
                        Campaign.title.ilike(f"%{query}%")
                    )
                )
                private_campaigns = Campaign.query.join(User).filter(
                    and_(
                        Campaign.visibility == 'Private',
                        User.role == 'sponsor',
                        User.niche == user.niche,
                        Campaign.title.ilike(f"%{query}%")
                    )
                )
                campaigns = public_campaigns.union(private_campaigns).all()

            elif filter_type == 'campaign_niche':
                public_campaigns = Campaign.query.join(User).filter(
                    and_(
                        Campaign.visibility == 'Public',
                        User.role == 'sponsor',
                        User.niche.ilike(f"%{query}%")
                    )
                )
                private_campaigns = Campaign.query.join(User).filter(
                    and_(
                        Campaign.visibility == 'Private',
                        User.role == 'sponsor',
                        User.niche == user.niche,
                        User.niche.ilike(f"%{query}%")
                    )
                )
                campaigns = public_campaigns.union(private_campaigns).all()

            elif filter_type == 'campaign_budget':
                public_campaigns = Campaign.query.filter(
                    and_(
                        Campaign.visibility == 'Public',
                        Campaign.budget >= float(query)
                    )
                )
                private_campaigns = Campaign.query.join(User).filter(
                    and_(
                        Campaign.visibility == 'Private',
                        User.role == 'sponsor',
                        User.niche == user.niche,
                        Campaign.budget >= float(query)
                    )
                )
                campaigns = public_campaigns.union(private_campaigns).all()
        else:
            # No filter applied, show all public campaigns and private campaigns matching niche
            public_campaigns = Campaign.query.filter_by(visibility='Public').all()
            niche_campaigns = Campaign.query.join(User).filter(
                and_(
                    Campaign.visibility == 'Private',
                    User.role == 'sponsor',
                    User.niche == user.niche,
                    Campaign.user_id == User.id
                )
            ).all()
            campaigns = public_campaigns + niche_campaigns
        return render_template('search.html', campaigns=campaigns, role='influencer')

    elif user.role == 'sponsor':
        if filter_type == 'influencer_name':
            influencers = User.query.filter(
                (User.role == 'influencer') & (User.name.ilike(f"%{query}%"))
            ).all()
        elif filter_type == 'influencer_niche':
            influencers = User.query.filter(
                (User.role == 'influencer') & (User.niche.ilike(f"%{query}%"))
            ).all()
        elif filter_type == 'influencer_social':
            influencers = User.query.filter(
                (User.role == 'influencer') & (User.socialnet.ilike(f"%{query}%"))  # Assuming socialnet represents followers or use the appropriate field
            ).all()
        
        else:
            influencers = User.query.filter_by(role='influencer', flag=False).all()
        return render_template('search.html', influencers=influencers, role='sponsor')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role')
        
        # Query user by username
        user = User.query.filter_by(username=username).first()
        
        # Check if user exists and password is correct
        if not user or not user.check_password(password):
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login'))
        
        # Check if the user is flagged
        if user.flag:
            flash("You can't log in because you have been flagged by the admin.", 'danger')
            return redirect(url_for('login'))
        
        # Check if the role matches
        if user.role != role:
            flash('Invalid role selected.', 'danger')
            return redirect(url_for('login'))

        # If everything is correct, set the session
        session['user_id'] = user.id
        return redirect(url_for('profile'))
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        role = request.form.get('role')
        if role == 'influencer':
            return redirect(url_for('register_influencer'))
        elif role == 'sponsor':
            return redirect(url_for('register_sponsor'))
    return render_template('registration.html')

@app.route('/register/influencer', methods=['GET', 'POST'])
def register_influencer():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        socialnet = request.form.get('socialnet')
        niche = request.form.get('niche')
        if User.query.filter_by(username=username).first():
            flash('Username already exists. Please choose another username.', 'danger')
            return redirect(url_for('register_influencer'))
        new_user = User(name=name, username=username, email=email, role='influencer', niche=niche, socialnet=socialnet)
        new_user.password = password
        db.session.add(new_user)
        db.session.commit()
        flash('Thank you for registering with us!', 'success')
        return redirect(url_for('login'))
    return render_template('register_influencer.html')

@app.route('/register/sponsor', methods=['GET', 'POST'])
def register_sponsor():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        industry = request.form['industry']
        
        if User.query.filter_by(username=username).first() or User.query.filter_by(email=email).first():
            flash('Username or email already exists.', 'danger')
            return redirect(url_for('register_sponsor'))
        new_user = User(name=name, username=username, email=email, role='sponsor', niche=industry)
        new_user.password = password
        db.session.add(new_user)
        db.session.commit()
        flash('Thank you for registering with us!', 'success')
        return redirect(url_for('login'))
    return render_template('register_sponsor.html')




@app.route('/send_ad_request', methods=['POST'])
@check_flagged_user
@login_required
def send_ad_request():
    user = User.query.get(session['user_id'])
    campaign_id = request.form.get('campaign_id')
    payment = request.form.get('payment')
    message = request.form.get('message')
    requirements = request.form.get('requirements')
    
    # Check if campaign_id is provided for influencer
    if user.role == 'influencer':
        campaign = Campaign.query.get_or_404(campaign_id)
        receiver_id = campaign.user_id
    else:
        receiver_id = request.form.get('receiver_id')
    
    ad_request = AdRequest(
        campaign_id=campaign_id,
        receiver_id=receiver_id,
        sender_id=user.id,
        message=message,
        requirements=requirements,
        payment=payment,
        status='Pending'
    )
    db.session.add(ad_request)
    db.session.commit()

    flash('Ad request sent successfully.', 'success')
    return redirect(url_for('search'))

from flask import flash, redirect, url_for, request

@app.route('/flag_user/<int:user_id>', methods=['POST'])
@login_required
def flag_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.flag = True
        db.session.commit()
        flash(f'{user.username} has been flagged.', 'success')
    return redirect(request.referrer)

@app.route('/unflag_user/<int:user_id>', methods=['POST'])
@login_required
def unflag_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.flag = False
        db.session.commit()
        flash(f'{user.username} has been unflagged.', 'success')
    return redirect(request.referrer)

@app.route('/flag_campaign/<int:campaign_id>', methods=['POST'])
@login_required
def flag_campaign(campaign_id):
    campaign = Campaign.query.get(campaign_id)
    if campaign:
        campaign.flag = True
        db.session.commit()
        flash(f'Campaign "{campaign.title}" has been flagged.', 'success')
    return redirect(request.referrer)

@app.route('/unflag_campaign/<int:campaign_id>', methods=['POST'])
@login_required
def unflag_campaign(campaign_id):
    campaign = Campaign.query.get(campaign_id)
    if campaign:
        campaign.flag = False
        db.session.commit()
        flash(f'Campaign "{campaign.title}" has been unflagged.', 'success')
    return redirect(request.referrer)


@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    user = User.query.get(user_id)
    
    if not user:
        flash('User not found.', 'error')
        return redirect(request.referrer)
    
    if user.role == 'influencer':
        # Check if the influencer is associated with any ad_requests
        ad_requests = AdRequest.query.filter(
            (AdRequest.sender_id == user_id) | (AdRequest.receiver_id == user_id)
        ).all()
        
        # Allow deletion only if all associated ad requests have status 'Pending' or 'Rejected'
        if all(req.status in ['Pending', 'Rejected'] for req in ad_requests):
            for req in ad_requests:
                db.session.delete(req)
            db.session.delete(user)
            db.session.commit()
            flash(f'Influencer {user.username} and associated ad requests have been deleted.', 'success')
        else:
            flash(f'Cannot delete {user.username} as they are associated with active ad requests.', 'danger')
    
    elif user.role == 'sponsor':
        # Check if the sponsor is associated with any campaigns
        campaigns = Campaign.query.filter_by(user_id=user_id).all()
        deletable = True
        
        for campaign in campaigns:
            ad_requests = AdRequest.query.filter_by(campaign_id=campaign.id).all()
            if not all(req.status in ['Pending', 'Rejected'] for req in ad_requests):
                deletable = False
                break
        
        if deletable:
            # Delete ad requests and campaigns associated with the sponsor
            for campaign in campaigns:
                ad_requests = AdRequest.query.filter_by(campaign_id=campaign.id).all()
                for req in ad_requests:
                    db.session.delete(req)
                db.session.delete(campaign)
            db.session.delete(user)
            db.session.commit()
            flash(f'Sponsor {user.username}, their campaigns, and associated ad requests have been deleted.', 'success')
        else:
            flash(f'Cannot delete {user.username} as they are associated with active campaigns or ad requests.', 'error')
    
    return redirect(request.referrer)


@app.route('/reviews')
@check_flagged_user
@login_required
def reviews():
    user = User.query.get(session['user_id'])

    reviews = Rating.query.filter_by(ratee_id=user.id).all()

    return render_template('reviews.html', user=user, reviews=reviews)


@app.route('/edit_ad_request/<int:request_id>', methods=['GET', 'POST'])
@check_flagged_user
def edit_ad_request(request_id):
    ad_request = AdRequest.query.get_or_404(request_id)

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        ad_request.message = request.form.get('message')
        ad_request.requirements = request.form.get('requirements')
        ad_request.payment = request.form.get('payment')

        db.session.commit()
        flash('Ad Request updated successfully!', 'success')
        return redirect(url_for('profile'))

    return render_template('edit_adrequest.html', ad_request=ad_request)

@app.route('/edit_campaign/<int:campaign_id>', methods=['GET', 'POST'])
@check_flagged_user
def edit_campaign(campaign_id):
    campaign = Campaign.query.get_or_404(campaign_id)
    

    if request.method == 'POST':
        # Update campaign details
        campaign.title = request.form.get('title')
        campaign.budget = float(request.form.get('budget'))
        campaign.description = request.form.get('description')

        # Convert date strings to datetime.date objects
        campaign.start_date = datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date()
        campaign.end_date = datetime.strptime(request.form.get('end_date'), '%Y-%m-%d').date()

        campaign.goals = request.form.get('goals')
        campaign.visibility = request.form.get('visibility')
        
        db.session.commit()
        flash('Campaign details updated successfully!', 'success')
        return redirect(url_for('profile'))

    return render_template('edit_campaign.html', campaign=campaign)


@app.route('/delete_campaign/<int:campaign_id>', methods=['POST'])
@check_flagged_user
def delete_campaign(campaign_id):
    # Fetch the campaign to be deleted
    campaign = Campaign.query.get_or_404(campaign_id)
    
    # Fetch all ad requests associated with the campaign
    ad_requests = campaign.ad_requests
    
    # Check if there are any ad requests that are not pending
    for ad_request in ad_requests:
        if ad_request.status != 'Pending':
            flash('Cannot delete campaign. There are ad-requests that are in progress', 'danger')
            return redirect(request.referrer)
    
    # If all ad requests are either pending or none exist, delete the campaign
    try:
        # Delete associated ad requests first
        for ad_request in ad_requests:
            db.session.delete(ad_request)
        
        # Delete the campaign
        db.session.delete(campaign)
        db.session.commit()
        flash('Campaign and associated ad requests deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting campaign: {str(e)}', 'danger')
    
    return redirect(url_for('campaigns'))

@app.route('/flagged_items')
@login_required
def flagged_items():
    flagged_campaigns = Campaign.query.filter_by(flag=True).all()
    flagged_sponsors = User.query.filter_by(role='sponsor', flag=True).all()
    flagged_influencers = User.query.filter_by(role='influencer', flag=True).all()
    return render_template('flagged.html', flagged_campaigns=flagged_campaigns, flagged_sponsors=flagged_sponsors, flagged_influencers=flagged_influencers)

@app.route('/unflag_all/<string:role>', methods=['POST','GET'])
@login_required
def unflag_all(role):
    if role == 'campaign':
        Campaign.query.filter_by(flag=True).update({'flag': False})
    elif role == 'sponsor':
        User.query.filter_by(role='sponsor', flag=True).update({'flag': False})
    elif role == 'influencer':
        User.query.filter_by(role='influencer', flag=True).update({'flag': False})
    
    db.session.commit()
    flash(f'All flagged {role}s have been unflagged.', 'success')
    return redirect(url_for('flagged_items'))

@app.route('/view_profile/<int:user_id>', methods=['GET'])
@app.route('/view_profile/<int:user_id>', methods=['GET'])
def view_profile(user_id):
    user = User.query.get_or_404(user_id)
    
    # Calculate average rating based on ratings received
    ratings = Rating.query.filter_by(ratee_id=user_id).all()
    avg_rating = None
    if ratings:
        avg_rating = sum(rating.rating for rating in ratings) / len(ratings)

    return render_template('view_profile.html', user=user, avg_rating=avg_rating)

@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

