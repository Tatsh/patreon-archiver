from typing import Final, Mapping

__all__ = ('FIELDS', 'MEDIA_URI', 'PATREON_API_URI', 'POSTS_URI', 'USER_AGENT')

PATREON_API_URI: Final[str] = 'https://www.patreon.com/api'
MEDIA_URI: Final[str] = f'{PATREON_API_URI}/media'
POSTS_URI: Final[str] = f'{PATREON_API_URI}/posts'
FIELDS: Final[Mapping[str, str]] = dict(
    campaign=','.join(
        ('currency', 'show_audio_post_download_links', 'avatar_photo_url',
         'earnings_visibility', 'is_nsfw', 'is_monthly', 'name', 'url')),
    post=','.join(('change_visibility_at', 'comment_count', 'content',
                   'current_user_can_comment', 'current_user_can_delete',
                   'current_user_can_view', 'current_user_has_liked', 'embed',
                   'image', 'is_paid', 'like_count', 'meta_image_url',
                   'min_cents_pledged_to_view', 'post_file', 'post_metadata',
                   'published_at', 'patreon_url', 'post_type', 'pledge_url',
                   'thumbnail_url', 'teaser_text', 'title', 'upgrade_url',
                   'url', 'was_posted_by_campaign_owner', 'has_ti_violation')),
    post_tag=','.join(('tag_type', 'value')),
    user=','.join(('image_url', 'full_name', 'url')),
    access_rule=','.join(('access_rule_type', 'amount_cents')),
    media=','.join(
        ('id', 'image_urls', 'download_url', 'metadata', 'file_name')),
    contains_exclusive_posts='true',
    is_draft='false')
USER_AGENT: Final[str] = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/100.0.4758.54 '
                          'Safari/537.36')
SHARED_PARAMS: Final[Mapping[str, str]] = {
    **dict(include=','.join((
        'campaign',
        'access_rules',
        'attachments',
        'audio',
        'images',
        'media',
        'poll.choices',
        'poll.current_user_responses.user',
        'poll.current_user_responses.choice',
        'poll.current_user_responses.poll',
        'user',
        'user_defined_tags',
        'ti_checks',
    )),
           sort='-published_at'),
    **{
        'filter[is_following]': 'true',
        'page[cursor]': 'null',
        'json-api-use-default-includes': 'false',
        'json-api-version': '1.0',
    },
    **{f'fields[{x}]': y
       for x, y in FIELDS.items()}
}
