export interface Posts {
  data: {
    attributes: {
      url: string;
    } & (
      | {
          post_type: 'audio_embed';
        }
      | {
          post_type: 'audio_file';
        }
      | {
          post_file: {
            name: string;
            url: string;
          };
          post_metadata: {
            image_order: string[];
          };
          post_type: 'image_file';
        }
      | {
          post_type: 'video_embed';
        }
    );
    id: string;
  }[];
  links: { next: string | null };
}

export interface Media {
  data: {
    attributes: {
      image_urls: {
        original: string;
      };
      mimetype: string;
    };
    id: string;
  };
}
