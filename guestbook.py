import os
import urllib
import json

from google.appengine.api import images
from google.appengine.api import users
from google.appengine.ext import ndb

import jinja2
import webapp2

from google.appengine.ext import blobstore
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.webapp.util import run_wsgi_app

## Import smtplib for the actual sending function
#import smtplib
#
## Import the email modules we'll need
#from email.mime.multipart import MIMEMultipart
#from email.mime.text import MIMEText
# http://webapp-improved.appspot.com/api/webapp2_extras/appengine/auth/models.html#webapp2_extras.appengine.auth.models.User
# webapp2_extras.appengine.auth.models.User(*args, **kwds)
# Link to example of a general user-auth solution:
# https://blog.abahgat.com/2013/01/07/user-authentication-with-webapp2-on-google-app-engine/

from google.appengine.api import mail


JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

DEFAULT_DISCUSSION_NAME = 'default_discussion'

# Setup several ndb entities
# Todo:  Make Owner and Author children of same parent
# https://cloud.google.com/appengine/docs/python/users/userobjects 
# http://blog.abahgat.com/2013/01/07/user-authentication-with-webapp2-on-google-app-engine/


class Author(ndb.Model):
    """Sub model for representing a comment author"""
    identity = ndb.StringProperty(indexed=False)
    email = ndb.StringProperty(indexed=False)

class Owner(ndb.Model):
    """Sub model for representing a discussion owner"""
    identity = ndb.StringProperty(indexed=False)
    email = ndb.StringProperty(indexed=False)

class Greeting(ndb.Model):
    """A main model for representing an individual comment entry."""
    author = ndb.StructuredProperty(Author)
    content = ndb.StringProperty(indexed=False)
    upvotes = ndb.IntegerProperty()
    upvote_ids = ndb.IntegerProperty(repeated=True) 
    downvotes = ndb.IntegerProperty()
    downvote_ids = ndb.IntegerProperty(repeated=True)
    date = ndb.DateTimeProperty(auto_now_add=True)
    num_comments = ndb.IntegerProperty()
    photos = ndb.BlobProperty(repeated=True)
    subcomment = ndb.BooleanProperty()
    
class Discussion(ndb.Model):
    """A main model for representing an individual discussion entry."""
    owner = ndb.StructuredProperty(Owner)
    title = ndb.StringProperty()
    content = ndb.StringProperty(indexed=False)
    upvotes = ndb.IntegerProperty()
    upvote_ids = ndb.IntegerProperty(repeated=True)    
    downvotes = ndb.IntegerProperty()
    downvote_ids = ndb.IntegerProperty(repeated=True)
    date = ndb.DateTimeProperty(auto_now_add=True)
    medical_category = ndb.StringProperty()
    num_comments = ndb.IntegerProperty()
    photos = ndb.BlobProperty(repeated=True)
    
class MrUser(ndb.Model):
    """A main model for local persistence of the logged-in user"""
    userid = ndb.StringProperty()
    # this is the key of the current discussion
    currentDiscussionKey = ndb.StringProperty()
    avatar = ndb.BlobProperty()
    upvotes = ndb.IntegerProperty()
    upvote_ids = ndb.IntegerProperty(repeated=True)
    downvotes = ndb.IntegerProperty()
    downvote_ids = ndb.IntegerProperty(repeated=True)
    num_comments = ndb.IntegerProperty()


class MainPage(webapp2.RequestHandler):
    def get(self):
        
        discussions = Discussion.query().order(-Discussion.date).fetch(100)           
        
        # If there are no discussions, create the welcome discussion
        if not discussions:
            discussion = Discussion(title='Welcome - What is medReach?', medical_category='general', num_comments=0)
            key = discussion.put()
            discussions = Discussion.query().fetch(100)
            greeting = Greeting(parent=key)
            greeting.author = Author(email='medReach')
            greeting.content = 'Welcome to medReach'
            greeting.put()
       
        # Get the medreach user entity (mrUser) associated to this google userID and update view state from the mrUser persistence
        user = users.get_current_user()
        if user:
            q = ndb.gql("SELECT * FROM MrUser WHERE userid = :1", user.user_id())
            mrUser = q.get()
            if not mrUser:
                mrUser = MrUser(userid = user.user_id(), avatar = None)  # Put the avatar default here
                mrUser.put()
            currentDiscussion = mrUser.currentDiscussionKey

        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
        

        template_values = {
            'user': user,
            'discussions': discussions,
#            'discussion_name': urllib.quote_plus(discussion_name),
            'url': url,
            'url_linktext': url_linktext,
        }
        
        template = JINJA_ENVIRONMENT.get_template('index.html')
        self.response.write(template.render(template_values))
        
class DiscussionPage(webapp2.RequestHandler):
    def get(self):
        #Convert the key string to an entity key
        discussion_key = self.request.get('discussion_key')
        key = ndb.Key(urlsafe=discussion_key)

        #Get the discussion
        discussion = key.get()
        discussion_title = discussion.title
        
        # Get the list of greetings in sorted order
        greetings = Greeting.query(ancestor=key).order(Greeting.date).fetch(100)
        
        # Create a jagged 2D list-of-lists with comments and sub-comments
        # Sub-greetings are discovered via their parent key relationship to the parent greeting
        greeting_list = []
        index = 0
        for greeting in greetings:
            if not greeting.subcomment:  # Skip the subcomments or you'll get duplicates
                greeting_list.append([])  # Append a list to the list to make it 2D
                subgreetings = Greeting.query(ancestor=greeting.key).order(Greeting.date).fetch(100)
                for subgreeting in subgreetings:
                    greeting_list[index].append(subgreeting)  # may have to iterate to add to this list
                index += 1               
    
        user = users.get_current_user()
        if user:
            q = ndb.gql("SELECT * FROM MrUser WHERE userid = :1", user.user_id())
            mrUser = q.get()
        else:
            mrUser = None

        #Get the upload endpoint URL for the photo upload
        upload_url = blobstore.create_upload_url('/discussion?discussion_key=' + key.urlsafe())

        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'

        template_values = {
            'user': user,
            'mr_user': mrUser,
            'greeting_list': greeting_list,
            'discussion': discussion,
            'discussion_title': discussion_title,
            'url': url,
            'url_linktext': url_linktext,
            'upload_url': upload_url,
        }

        template = JINJA_ENVIRONMENT.get_template('discussion.html')
        self.response.write(template.render(template_values))

class Avatar(webapp2.RequestHandler):
    def get(self):   
        image_id = self.request.get('img_id')

        user = users.get_current_user()        
        
        # The image id is the greeting key
        if  image_id != None and image_id != 'None':
            greeting_key = ndb.Key(urlsafe=image_id)
            greeting = greeting_key.get()
            authorId = greeting.author.identity
            
            # This query gets the medreach user associated to the authorID which is a google userID
            q = ndb.gql("SELECT * FROM MrUser WHERE userid = :1", authorId)
            mrUser = q.get()
        elif image_id == None or image_id == 'None' and user:
            # If there is no greeting, then use the current users's avatar
            q = ndb.gql("SELECT * FROM MrUser WHERE userid = :1", user.user_id())
            mrUser = q.get()
        else:
            mrUser = None
        
        if mrUser and mrUser.avatar:
            self.response.headers['Content-Type'] = 'image/png'
            self.response.out.write(mrUser.avatar)
        else:
            self.response.out.write('No image')
            
class PostAvatar(webapp2.RequestHandler):
    def post(self):
        try:
            user = users.get_current_user()

            if user:
                q = ndb.gql("SELECT * FROM MrUser WHERE userid = :1", user.user_id())
                mrUser = q.get()
            else:
                self.response.out.write('Please Login')

            if self.request.get('img'):
                avatar = self.request.get('img')
                avatar = images.resize(avatar, 32, 32)
                mrUser.avatar = avatar
                mrUser.put()
            else:
                mrUser.avatar = Null  #Null is used as a switch for the glyph
                mrUser.put()

            self.redirect('/settings')
        except:
            self.error(500)

# DeleteDiscussion - can be when the last greeting is deleted or it can be a single delete function with a parameter.
# Or it can be based on the key type - can that be discovered?
class DeleteEntity(webapp2.RequestHandler):
    def post(self):
        try:
            del_type = self.request.get('del_type')
#            discussion_id = self.request.get('discussion_id',
#                                               DEFAULT_DISCUSSION_NAME)
            discussion_key = self.request.get('discussion_key')
            disc_key = ndb.Key(urlsafe=discussion_key)
            discussion = disc_key.get()
            
            if del_type == 'discussion':
                disc_key.delete()
                self.redirect('/')
                
            elif del_type == 'greeting':
                if discussion.num_comments > 0:
                    discussion.num_comments -= 1
                    discussion.put()

                greeting_key = self.request.get('greeting_key')
                key = ndb.Key(urlsafe=greeting_key)
                key.delete()

                greetings = Greeting.query(ancestor=disc_key).fetch(100) 
                if not greetings:
                    # If you want to automatically remove a discussion when there are
                    # no comments left, uncomment the two lines below and remove the redirect
#                    disc_key.delete()
#                    self.redirect('/')
                    self.redirect('/discussion?discussion_key=' + disc_key.urlsafe())
                else:
                    self.redirect('/discussion?discussion_key=' + disc_key.urlsafe())
        except:
            self.error(500)

class PostDiscussion(webapp2.RequestHandler):
    def post(self):
        try:
            if self.request.get('disc-title'):
                discussion_title = self.request.get('disc-title')
            else:
                discussion_title = 'Title'
            if self.request.get('content'):
                discussion_body = self.request.get('content')
            else:
                discussion_body = 'Comment'
            discussion_category = self.request.get('medical-category')
            discussion = Discussion(title = discussion_title, upvotes=0, downvotes=0, medical_category=discussion_category, num_comments=0, content=discussion_body)
            
            if users.get_current_user():
                discussion.owner = Owner(
                        identity=users.get_current_user().user_id(),
                        email=users.get_current_user().email())
            else:
                discussion.owner = Owner(email='anonymous')
                
            if discussion.title:
                key = discussion.put()
                self.redirect('/discussion?discussion_key=' + key.urlsafe())
            else:
                self.redirect('/')
        except:
            self.error(500)
            
class UpdateDiscussion(webapp2.RequestHandler):
    def post(self):
#        try:
            discussion_key = self.request.get('discussion_key')
            disc_key = ndb.Key(urlsafe=discussion_key)
            discussion = disc_key.get()
            
            if self.request.get('content'):
                discussion.content = self.request.get('content')
            if self.request.get('disc-title'):
                discussion.title = self.request.get('disc-title')
            if self.request.get('medical-category'):
                discussion.medical_category = self.request.get('medical-category')
                
            discussion.put()
            self.redirect('/discussion?discussion_key=' + discussion.key.urlsafe())

#        except:
#            self.error(500)
            
class PostGreeting(webapp2.RequestHandler):
    def post(self):
#        try:
            discussion_key = self.request.get('discussion_key')
            disc_key = ndb.Key(urlsafe=discussion_key)
            discussion = disc_key.get()
            
            # Get the discussion and update the comment count
            parent_key = self.request.get('key')
            key = ndb.Key(urlsafe=parent_key)
            parent = key.get()
            if discussion.num_comments == None:
                discussion.num_comments = 0
            discussion.num_comments += 1
#            if self.request.get('parent') == 'discussion':
#                #parent is a discussion
#                #todo:  fix this - this can be polymorphic
#                discussion = parent

            # Instantiate a new greeting with parent set to either discussion or comment
            if self.request.get('parent') == 'discussion':
                greeting = Greeting(parent=key, upvotes=0, downvotes=0, subcomment=False)
            elif self.request.get('parent') == 'greeting':
                greeting = Greeting(parent=key, upvotes=0, downvotes=0, subcomment=True)

            # Set the author ID
            user = users.get_current_user()
            if user:
                greeting.author = Author(
                        identity=users.get_current_user().user_id(),
                        email=users.get_current_user().email())
                q = ndb.gql("SELECT * FROM MrUser WHERE userid = :1", user.user_id())
                mrUser = q.get()
                
                # Set the avatar (if present)
                if self.request.get('img'):
                    avatar = self.request.get('img')
                    avatar = images.resize(avatar, 32, 32)
                    mrUser.avatar = avatar
                    
                # Update the users comment count
                if mrUser:
                    if mrUser.num_comments == None:
                        mrUser.num_comments = 0
                    mrUser.num_comments += 1
                    mrUser.put()
                
                    
            # Set the content
            greeting.content = self.request.get('content')

#            # Send email notification
#            # Create message container - the correct MIME type is multipart/alternative.
##            msg = MIMEMultipart('alternative')
#            msg = MIMEText(greeting.content)
#            msg['Subject'] = "Someone Responded to You on medReach"
            sender_addr = 'glengoffin3@gmail.com'
#            sender_addr = 'noreply@medreach.appspotmail.com'
#            sender_addr = 'medreach-1080@appspot.gserviceaccount.com'
#            sender_addr = 'medreach-1080@appspot.gserviceaccount.com'
            url_link = 'http://medreach-1080.appspot.com/discussion?discussion_key=' + discussion.key.urlsafe()
#            msg['From'] = sender
            if discussion.owner and discussion.owner != 'anonymous':
                recipient_addr = discussion.owner.email
                print discussion.owner.email
            else:
                recipient_addr = None
                
#            html = """\
#                    <html>
#                      <head></head>
#                      <body>
#                        <p>Hi!<br>
#                           %s has responded to your post titled: "%s"<br>
#                           Here's what they said: "%s"
#                           Visit the site %s
#                        </p>
#                      </body>
#                    </html>
#                    """ % (greeting.author.email, discussion.title, greeting.content, url_link)
#            
#            text = ("""%s has responded to your post titled, " %s "  \nHere's what they said: " %s "  \nVisit the site %s.
#                    """ % (greeting.author.email, discussion.title, greeting.content, url_link))

                
#            msg['To'] = recipient
#
#            # Send the message via our own SMTP server, but don't include the
#            # envelope header.
#            try:
#                s = smtplib.SMTP('localhost')
#                s.sendmail(sender, recipient, msg.as_string())
#                s.quit()
#            except Exception, e: 
#                print e
#                print 'ERROR: Unable to send email'
            if not user or user.user_id() == recipient_addr or recipient_addr == None:
                print 'no email'
            else:
                try:    
                    mail.send_mail(sender=sender_addr,
                                  to=recipient_addr,
                                  subject="%s Replied to You on MedReach" % greeting.author.email,
                                  body="""%s has responded to your post titled, "%s"  \nHere's what they said: "%s"  \nVisit the site %s.
                                        """ % (greeting.author.email, discussion.title, greeting.content, url_link))
                except Exception, e:
                    print e
                    print 'Error: Unable to send email'
#            """
#            Dear Albert:
#
#            Your example.com account has been approved.  You can now visit
#            http://www.example.com/ and sign in using your Google Account to
#            access new features.
#
#            Please let us know if you have any questions.
#
#            The example.com Team
#            """
                

            greeting.put()
            discussion.put()  # Updates to num_comments needed to be posted

            self.redirect('/discussion?discussion_key=' + discussion.key.urlsafe())
#        except:
#            self.error(500)

#Todo:  Change this to GetPhoto()
class Photo(webapp2.RequestHandler):
    def get(self):
        #The imageID is the greeting ID
        entity_key = ndb.Key(urlsafe=self.request.get('img_id'))
        entity = entity_key.get()
        
        #Problem: Need the iterator to know which index into the list?
        loop_index = int(self.request.get('loop_index'))
        loop_index -= 1

        if entity.photos[loop_index]:
            self.response.headers['Content-Type'] = 'image/png'
            self.response.out.write(entity.photos[loop_index])
        else:
            self.response.out.write('No image')

class PostPhoto(webapp2.RequestHandler):
    def post(self):
        try:
            discussion_key = self.request.get('discussion_key')
            disc_key = ndb.Key(urlsafe=discussion_key)
            discussion = disc_key.get()
            
            greeting_key = self.request.get('greeting_key')
            key = ndb.Key(urlsafe=greeting_key)
            greeting = key.get()

            #Add photo to greeting entity
            if self.request.get('photo'):
                photo = self.request.get('photo')
                photo = images.resize(photo, width=400)
                greeting.photos.append(photo)
            
                #Add smaller version of photo to discussion gallery
                photo = images.resize(photo, 130, 160)
                discussion.photos.append(photo)
            
                greeting.put()
                discussion.put()

            self.redirect('/discussion?discussion_key=' + disc_key.urlsafe())
        except:
            self.error(500)

#  TODO: Need to find way to print to console in python
#  Need to print the userID and blobKey
class Vote(webapp2.RequestHandler):
    def post(self):
#        try:
            discussion_key = self.request.get('discussion_key')
            disc_key = ndb.Key(urlsafe=discussion_key)
        
            greeting_key = self.request.get('greeting_key')
            key = ndb.Key(urlsafe=greeting_key)
            greeting = key.get()
            
            #Find the mrUser associatd to this google userID
#            if greeting.author.identity:
            # Set the author ID
            user = users.get_current_user()
            if user:
                q = ndb.gql("SELECT * FROM MrUser WHERE userid = :1", user.user_id())
                mrUser = q.get()
            else:
                mrUser = None
                
            #Check to see if this person has already voted           
            allow_vote = True
            if mrUser != None:
                for upvote_id in greeting.upvote_ids:
                    if upvote_id == mrUser.key.id():
                        allow_vote = False
                for downvote_id in greeting.downvote_ids:
                    if downvote_id == mrUser.key.id():
                        allow_vote = False
            else:
                allow_vote = False
                 
            #Save the identities of the voters with the comment
            if self.request.get('vote_type') == 'up':
                
                if allow_vote:
                    greeting.upvote_ids.append(mrUser.key.id())
                    if greeting.upvotes == None:
                        greeting.upvotes = 1
                    else:
                        greeting.upvotes += 1
                        
                    mrUser.upvote_ids.append(greeting.key.id())
                    if mrUser.upvotes == None:
                        mrUser.upvotes = 1
                    else:
                        mrUser.upvotes += 1
                        
            elif self.request.get('vote_type') == 'down':
                
                if allow_vote:
                    greeting.downvote_ids.append(mrUser.key.id())
                    if greeting.downvotes == None:
                        greeting.downvotes = 1
                    else:
                        greeting.downvotes += 1
                        
                    mrUser.downvote_ids.append(greeting.key.id())
                    if mrUser.downvotes == None:
                        mrUser.downvotes = 1
                    else:
                        mrUser.downvotes += 1
            
            greeting.put()
            if mrUser:
                mrUser.put()
            
            self.redirect('/discussion?discussion_key=' + disc_key.urlsafe())

#        except:
#            self.error(500)



class AboutPage(webapp2.RequestHandler):
    def get(self):

        template = JINJA_ENVIRONMENT.get_template('about.html')
        self.response.write(template.render())

class SettingsPage(webapp2.RequestHandler):
    def get(self):

        user = users.get_current_user()
        
        # Find the mrUser record associated with this google userID
        if user:
            q = ndb.gql("SELECT * FROM MrUser WHERE userid = :1", user.user_id())
            mrUser = q.get() 
            if self.request.get('img'):
                avatar = self.request.get('img')
                avatar = images.resize(avatar, 32, 32)
                mrUser.avatar = avatar
                mrUser.put()
        else:
            mrUser = None

        if user:
            url = users.create_logout_url(self.request.uri)
            url_linktext = 'Logout'
        else:
            url = users.create_login_url(self.request.uri)
            url_linktext = 'Login'
        
        template_values = {
            'user': user,
            'mrUser': mrUser,
            'url': url,
            'url_linktext': url_linktext,
        }
        
        template = JINJA_ENVIRONMENT.get_template('settings.html')
        self.response.write(template.render(template_values))
        

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/discussion', DiscussionPage),
    ('/about', AboutPage),
    ('/settings', SettingsPage),
    ('/img', Avatar),
    ('/upload_avatar', PostAvatar),
    ('/upload_img', PostPhoto),
    ('/photo', Photo),
    ('/post_new', PostDiscussion),
    ('/update', UpdateDiscussion),
    ('/sign', PostGreeting),
    ('/delete', DeleteEntity),
    ('/vote', Vote),
], debug=True)
