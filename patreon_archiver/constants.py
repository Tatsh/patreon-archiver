from typing import Final, Mapping

__all__ = ('FIELDS', 'MEDIA_URI', 'PATREON_API_URI', 'POSTS_URI',
           'SHARED_HEADERS', 'USER_AGENT')

PATREON_API_URI: Final[str] = 'https://www.patreon.com/api'
MEDIA_URI: Final[str] = f'{PATREON_API_URI}/media'
POSTS_URI: Final[str] = f'{PATREON_API_URI}/posts'
FIELDS: Final[Mapping[str, str]] = dict(
    campaign=','.join(
        ('avatar_photo_url', 'currency', 'earnings_visibility', 'is_monthly',
         'is_nsfw', 'name', 'show_audio_post_download_links', 'url')),
    post=','.join(
        ('change_visibility_at', 'comment_count', 'content',
         'current_user_can_comment', 'current_user_can_delete',
         'current_user_can_view', 'current_user_has_liked', 'embed',
         'has_ti_violation', 'image', 'is_paid', 'like_count',
         'meta_image_url', 'min_cents_pledged_to_view', 'patreon_url',
         'pledge_url', 'post_file', 'post_metadata', 'post_type',
         'published_at', 'teaser_text', 'thumbnail_url', 'title',
         'upgrade_url', 'url', 'was_posted_by_campaign_owner')),
    post_tag=','.join(('tag_type', 'value')),
    user=','.join(('image_url', 'full_name', 'url')),
    access_rule=','.join(('access_rule_type', 'amount_cents')),
    media=','.join(
        ('download_url', 'file_name', 'id', 'image_urls', 'metadata')),
    contains_exclusive_posts='true',
    is_draft='false')
USER_AGENT: Final[str] = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/100.0.4758.54 '
                          'Safari/537.36')
SHARED_HEADERS: Final[Mapping[str, str]] = {
    'accept': '*/*',
    'accept-language': 'en,en-GB;q=0.9,en-US;q=0.8',
    'authority': 'www.patreon.com',
    'cache-control': 'no-cache',
    'content-type': 'application/vnd.api+json',
    'dnt': '1',
    'pragma': 'no-cache',
    'referer': 'https://www.patreon.com/home',
    'user-agent': USER_AGENT,
}
SHARED_PARAMS: Final[Mapping[str, str]] = {
    **dict(include=','.join((
        'access_rules',
        'attachments',
        'audio',
        'campaign',
        'images',
        'media',
        'poll.choices',
        'poll.current_user_responses.choice',
        'poll.current_user_responses.poll',
        'poll.current_user_responses.user',
        'ti_checks',
        'user',
        'user_defined_tags',
    )),
           sort='-published_at'),
    **{
        'json-api-version': '1.0',
    },
    **{f'fields[{x}]': y
       for x, y in FIELDS.items()}
}
