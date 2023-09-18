# BASE CLASS

## base class

### Content(ScrapingMixin)

Attributes

* id
* poster_id
* poster_name
* url
* title
* thumbnail
* posted_at
* updated_at
* tags
* is_deleted

Methods

* __init_
* __str_
* __repr_
* __setattr_
* __eq_
* from_dict
* to_dict

### Video(Content)

Attributes

* id
* poster_id
* poster_name
* url
* title
* thumbnail
* posted_at
* updated_at
* tags
* is_deleted

* description
* duration
* view_count
* like_count
* comment_count

Methods

* __init_
* set_value
* update_value

### Live(Content)

Attributes

* id
* poster_id
* poster_name
* url
* title
* thumbnail
* posted_at
* updated_at
* tags
* is_deleted

* description
* duration
* view_count
* like_count
* comment_count

* start_at
* end_at
* status
* archive_enabled_at

Methods

* __init_
* set_value
* update_value

### News(Content)

Attributes

* id
* poster_id
* poster_name
* url
* title
* thumbnail
* posted_at
* updated_at
* tags
* is_deleted

* body

Methods

* __init_
* set_value
* update_value

## NicoNico

### NicoNico.Video(Video)

Methods

* from_id
* get_detail

### NicoNico.Live(Live)

Methods

* from_id
* get_detail

### NicoNico.Channel.News(News)

Methods

* super __init_
* from_id
* get_detail
