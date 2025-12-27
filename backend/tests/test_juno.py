import unittest
from unittest.mock import MagicMock, patch
from mp3_autotagger.clients.juno import JunoClient
from mp3_autotagger.core.models import Track

class TestJunoClient(unittest.TestCase):
    def setUp(self):
        self.client = JunoClient()
        
    @patch('mp3_autotagger.clients.juno.cloudscraper.create_scraper')
    def test_search_track_parsing(self, mock_scraper_creator):
        """
        Test that the client correctly parses the HTML structure we expect.
        """
        # Mock the scraper instance and its get method
        mock_scraper = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        # Simulated HTML based on Juno templates
        html_content = """
        <html>
        <body>
            <div class="jw-item">
                <div class="jw-image">
                    <img src="//wwwcdn.junodownload.com/images/1.jpg">
                </div>
                <div class="jw-artist">
                    Solomun
                </div>
                <div class="jw-title-container">
                    <a href="/products/solomun-the-way-back/1234567-02/" class="jw-title">
                        The Way Back
                    </a>
                </div>
                <div class="jw-label-container">
                    <a href="/labels/Diynamic" class="jw-label">
                        Diynamic
                    </a>
                </div>
            </div>
            
            <div class="jw-item">
                <div class="jw-artist">
                    Other Artist
                </div>
                <a href="/products/other/123/" class="jw-title">
                    Irrelevant Track
                </a>
            </div>
        </body>
        </html>
        """
        mock_response.text = html_content
        mock_scraper.get.return_value = mock_response
        
        # Inject the mock scraper into the client
        self.client.scraper = mock_scraper
        
        # Run search
        results = self.client.search_track("Solomun", "The Way Back")
        
        # Assertions
        self.assertEqual(len(results), 2) # Both items parsed, score filtering might have kept both depending on logic
        
        top_match = results[0]
        self.assertEqual(top_match.artist, "Solomun")
        self.assertEqual(top_match.title, "The Way Back")
        self.assertEqual(top_match.label, "Diynamic")
        self.assertEqual(top_match.cover_url, "https://wwwcdn.junodownload.com/images/1.jpg")
        self.assertEqual(top_match.source, "Juno")
        
        # Verify URL construction
        self.assertIn("https://www.junodownload.com/search/", self.client.SEARCH_URL)

if __name__ == '__main__':
    unittest.main()
