package kh.edu.kkhs.attendance;

import android.annotation.SuppressLint;
import android.content.Context;
import android.content.DialogInterface;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.net.Uri;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.Toast;

import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatActivity;
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout;

public class MainActivity extends AppCompatActivity {

    private WebView webView;
    private SwipeRefreshLayout swipeRefresh;
    private ProgressBar progressBar;
    private ValueCallback<Uri[]> uploadMessage;
    public static final int REQUEST_SELECT_FILE = 100;
    private static final String PREFS_NAME = "KKHS_APP_PREFS";
    private static final String KEY_SERVER_URL = "server_url";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        webView = findViewById(R.id.webView);
        swipeRefresh = findViewById(R.id.swipeRefreshLayout);
        progressBar = findViewById(R.id.progressBar);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setAllowFileAccess(true);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_ALWAYS_ALLOW);
        settings.setCacheMode(WebSettings.LOAD_DEFAULT);
        settings.setSupportZoom(true);
        settings.setBuiltInZoomControls(false);
        settings.setUserAgentString(settings.getUserAgentString() + " KKHS_Android_App/1.0");

        swipeRefresh.setOnRefreshListener(() -> webView.reload());
        swipeRefresh.setColorSchemeColors(getResources().getColor(R.color.accent));

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                progressBar.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progressBar.setVisibility(View.GONE);
                swipeRefresh.setRefreshing(false);
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) {
                    showOfflinePage();
                }
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progressBar.setProgress(newProgress);
            }

            @Override
            public boolean onShowFileChooser(WebView webView, ValueCallback<Uri[]> filePathCallback, FileChooserParams fileChooserParams) {
                if (uploadMessage != null) {
                    uploadMessage.onReceiveValue(null);
                    uploadMessage = null;
                }
                uploadMessage = filePathCallback;
                Intent intent = fileChooserParams.createIntent();
                try {
                    startActivityForResult(intent, REQUEST_SELECT_FILE);
                } catch (Exception e) {
                    uploadMessage = null;
                    Toast.makeText(MainActivity.this, "មិនអាចបើកកម្មវិធីរើសឯកសារបានទេ", Toast.LENGTH_SHORT).show();
                    return false;
                }
                return true;
            }
        });

        // Load Portal URL
        String targetUrl = getServerUrl();
        webView.loadUrl(targetUrl);
    }

    private String getServerUrl() {
        SharedPreferences prefs = getSharedPreferences(PREFS_NAME, MODE_PRIVATE);
        return prefs.getString(KEY_SERVER_URL, getString(R.string.default_portal_url));
    }

    public void configureServerUrl() {
        AlertDialog.Builder builder = new AlertDialog.Builder(this);
        builder.setTitle("កំណត់ Server URL (IP Address)");
        final EditText input = new EditText(this);
        input.setText(getServerUrl());
        builder.setView(input);

        builder.setPositiveButton("រក្សាទុក", (dialog, which) -> {
            String newUrl = input.getText().toString().trim();
            if (!newUrl.isEmpty()) {
                SharedPreferences.Editor editor = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).edit();
                editor.putString(KEY_SERVER_URL, newUrl);
                editor.apply();
                webView.loadUrl(newUrl);
            }
        });
        builder.setNegativeButton("បោះបង់", null);
        builder.show();
    }

    private void showOfflinePage() {
        String html = "<!DOCTYPE html><html lang='km'><head><meta charset='utf-8'>"
                + "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
                + "<style>body{background:#0F172A;color:#fff;font-family:sans-serif;text-align:center;padding:50px 20px;}"
                + ".card{background:#1E293B;padding:24px;border-radius:16px;box-shadow:0 4px 15px rgba(0,0,0,0.5);}"
                + "h2{color:#60A5FA;margin-bottom:10px;}p{color:#94A3B8;font-size:14px;line-height:1.6;}"
                + ".btn{display:inline-block;padding:10px 20px;margin:8px 4px;background:#2563EB;color:#fff;border-radius:8px;text-decoration:none;font-weight:bold;}"
                + ".btn-outline{background:transparent;border:1px solid #60A5FA;color:#60A5FA;}"
                + "</style></head><body><div class='card'>"
                + "<div style='font-size:48px;margin-bottom:12px;'>📡</div>"
                + "<h2>មិនអាចតភ្ជាប់ទៅកាន់ Server បានទេ</h2>"
                + "<p>សូមពិនិត្យមើលថា Server របស់សាលាបានបើកដំណើរការ ឬពិនិត្យ Wi-Fi / IP Address ឡើងវិញ។</p>"
                + "<a href='javascript:location.reload()' class='btn'>ព្យាយាមម្តងទៀត</a>"
                + "</div></body></html>";
        webView.loadDataWithBaseURL(null, html, "text/html", "UTF-8", null);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_SELECT_FILE) {
            if (uploadMessage == null) return;
            uploadMessage.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultCode, data));
            uploadMessage = null;
        }
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        if (keyCode == KeyEvent.KEYCODE_BACK && webView.canGoBack()) {
            webView.goBack();
            return true;
        }
        return super.onKeyDown(keyCode, event);
    }
}
