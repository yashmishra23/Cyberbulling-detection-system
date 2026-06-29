import React, { useState, useEffect, useRef } from 'react';
import { 
  ShieldAlert, 
  MessageSquare, 
  BarChart3, 
  Cpu, 
  Search, 
  Send, 
  Trash2, 
  AlertTriangle, 
  CheckCircle, 
  User, 
  RefreshCw, 
  Clock, 
  Heart, 
  Languages, 
  TrendingUp, 
  AlertOctagon, 
  Globe,
  LogOut
} from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Doughnut, Line, Bar } from 'react-chartjs-2';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

function Dashboard({ onLogout }) {
  const [activeTab, setActiveTab] = useState('analyzer');
  const [apiOnline, setApiOnline] = useState(false);
  const [apiLoading, setApiLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState(null);

  // Single Comment Analyzer State
  const [inputComment, setInputComment] = useState('');
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // Live Chat Simulation State
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [revealedMessages, setRevealedMessages] = useState(new Set());
  const [chatUser, setChatUser] = useState('You');
  const chatEndRef = useRef(null);

  // Admin Dashboard Analytics State
  const [analytics, setAnalytics] = useState({
    total_comments: 0,
    toxic_comments: 0,
    clean_comments: 0,
    categories: {},
    sentiment: {},
    languages: {},
    trends: [],
    top_abusive_words: []
  });

  // Logs & Model Info State
  const [logs, setLogs] = useState([]);
  const [logsSearch, setLogsSearch] = useState('');



  // Load current user from localStorage
  useEffect(() => {
    const user = localStorage.getItem('user');
    if (user) {
      const parsed = JSON.parse(user);
      setCurrentUser(parsed);
      setChatUser(parsed.name || parsed.email || 'You');
    }
  }, []);

  // 1. Check API Health and Load Initial Data
  const checkHealth = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/`);
      const data = await response.json();
      if (data.status === 'online') {
        setApiOnline(true);
      } else {
        setApiOnline(false);
      }
    } catch (error) {
      setApiOnline(false);
    } finally {
      setApiLoading(false);
    }
  };

  const fetchDashboardData = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/analytics`);
      const data = await response.json();
      setAnalytics(data);
    } catch (error) {
      console.error('Error fetching analytics:', error);
    }
  };

  const fetchLogs = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/logs`);
      const data = await response.json();
      setLogs(data);
    } catch (error) {
      console.error('Error fetching logs:', error);
    }
  };

  const fetchChatMessages = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/messages`);
      const data = await response.json();
      setChatMessages(data);
    } catch (error) {
      console.error('Error fetching chat messages:', error);
    }
  };

  useEffect(() => {
    checkHealth();
    fetchDashboardData();
    fetchLogs();
    fetchChatMessages();
    
    // Check health every 10 seconds
    const healthTimer = setInterval(checkHealth, 10000);
    return () => clearInterval(healthTimer);
  }, []);

  // Sync data when tabs change
  useEffect(() => {
    if (activeTab === 'dashboard') {
      fetchDashboardData();
    } else if (activeTab === 'metrics') {
      fetchLogs();
    } else if (activeTab === 'chat') {
      fetchChatMessages();
    }
  }, [activeTab]);

  // Scroll to bottom of chat
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatMessages, activeTab]);




  // 2. Event Handlers
  const handleAnalyze = async (e) => {
    e.preventDefault();
    if (!inputComment.trim()) return;

    setAnalysisLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: inputComment })
      });
      const data = await response.json();
      setAnalysisResult(data);
      fetchDashboardData(); // Sync dashboard in background
    } catch (error) {
      console.error('Error analyzing comment:', error);
    } finally {
      setAnalysisLoading(false);
    }
  };

  const handleSendChatMessage = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const msgText = chatInput;
    setChatInput('');

    try {
      await fetch(`${API_BASE_URL}/api/chat/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sender: chatUser, text: msgText })
      });
      fetchChatMessages();
      fetchDashboardData();
    } catch (error) {
      console.error('Error sending chat message:', error);
    }
  };

  const handleClearLogs = async () => {
    if (window.confirm('Are you sure you want to clear all analytics history?')) {
      try {
        await fetch(`${API_BASE_URL}/api/logs/clear`, { method: 'POST' });
        fetchLogs();
        fetchDashboardData();
      } catch (error) {
        console.error('Error clearing logs:', error);
      }
    }
  };

  const toggleRevealMessage = (index) => {
    const next = new Set(revealedMessages);
    if (next.has(index)) {
      next.delete(index);
    } else {
      next.add(index);
    }
    setRevealedMessages(next);
  };

  // 3. Setup Chart Data Configurations
  const prepareDoughnutData = () => {
    const categories = { ...analytics.categories };
    delete categories['Normal']; // Only show distribution of toxic categories for visual clarity
    
    const labels = Object.keys(categories);
    const data = Object.values(categories);

    return {
      labels: labels.length ? labels : ['No Cyberbullying Recorded'],
      datasets: [
        {
          data: data.length ? data : [0],
          backgroundColor: [
            'rgba(239, 68, 68, 0.7)',  // Hate Speech (Danger Red)
            'rgba(245, 158, 11, 0.7)',  // Threat (Warning Amber)
            'rgba(139, 92, 246, 0.7)',  // Harassment (Primary Purple)
            'rgba(59, 130, 246, 0.7)',   // Religious Abuse (Info Blue)
            'rgba(236, 72, 153, 0.7)',   // Gender Abuse (Pink)
          ],
          borderColor: 'rgba(255, 255, 255, 0.1)',
          borderWidth: 1.5,
        },
      ],
    };
  };

  const prepareLineData = () => {
    const dates = analytics.trends.map(t => {
      // Format YYYY-MM-DD to Short Date format (e.g. Jun 15)
      const d = new Date(t.date);
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });
    const totals = analytics.trends.map(t => t.total);
    const toxics = analytics.trends.map(t => t.toxic);

    return {
      labels: dates,
      datasets: [
        {
          label: 'Total Comments',
          data: totals,
          borderColor: 'rgba(139, 92, 246, 0.8)',
          backgroundColor: 'rgba(139, 92, 246, 0.15)',
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointBackgroundColor: '#8b5cf6',
        },
        {
          label: 'Toxic Intercepts',
          data: toxics,
          borderColor: 'rgba(239, 68, 68, 0.8)',
          backgroundColor: 'rgba(239, 68, 68, 0.1)',
          fill: true,
          tension: 0.4,
          pointRadius: 4,
          pointBackgroundColor: '#ef4444',
        }
      ]
    };
  };

  const prepareBarData = () => {
    const sentiments = analytics.sentiment;
    const labels = ['Positive', 'Neutral', 'Negative'];
    const data = [
      sentiments['Positive'] || 0,
      sentiments['Neutral'] || 0,
      sentiments['Negative'] || 0,
    ];

    return {
      labels,
      datasets: [
        {
          label: 'Comments Count',
          data,
          backgroundColor: [
            'rgba(16, 185, 129, 0.65)', // Positive (Emerald)
            'rgba(59, 130, 246, 0.65)',  // Neutral (Blue)
            'rgba(239, 68, 68, 0.65)'    // Negative (Crimson)
          ],
          borderColor: 'rgba(255, 255, 255, 0.08)',
          borderWidth: 1,
          borderRadius: 8
        }
      ]
    };
  };

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: {
          color: '#94a3b8',
          font: { family: 'Outfit', size: 12 }
        }
      },
      tooltip: {
        titleFont: { family: 'Outfit' },
        bodyFont: { family: 'Outfit' }
      }
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: '#64748b', font: { family: 'Outfit' } }
      },
      y: {
        grid: { color: 'rgba(255, 255, 255, 0.04)' },
        ticks: { color: '#64748b', font: { family: 'Outfit' }, stepSize: 1 }
      }
    }
  };

  const filteredLogs = logs.filter(log => 
    log.text.toLowerCase().includes(logsSearch.toLowerCase()) ||
    log.category.toLowerCase().includes(logsSearch.toLowerCase()) ||
    log.sentiment.toLowerCase().includes(logsSearch.toLowerCase()) ||
    log.language.toLowerCase().includes(logsSearch.toLowerCase())
  );

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <nav className="sidebar">
        <div className="logo-container">
          <ShieldAlert size={28} className="logo-icon" />
          <span className="logo-text">SafeSpace AI</span>
        </div>
        
        <ul className="nav-links">
          <li>
            <div 
              className={`nav-item ${activeTab === 'analyzer' ? 'active' : ''}`}
              onClick={() => setActiveTab('analyzer')}
            >
              <Search size={18} />
              <span>Text Analyzer</span>
            </div>
          </li>
          <li>
            <div 
              className={`nav-item ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              <MessageSquare size={18} />
              <span>Live Chat Sim</span>
            </div>
          </li>
          {currentUser?.is_admin && (
            <>
              <li>
                <div 
                  className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
                  onClick={() => setActiveTab('dashboard')}
                >
                  <BarChart3 size={18} />
                  <span>Admin Dashboard</span>
                </div>
              </li>
              <li>
                <div 
                  className={`nav-item ${activeTab === 'metrics' ? 'active' : ''}`}
                  onClick={() => setActiveTab('metrics')}
                >
                  <Cpu size={18} />
                  <span>Model & Logs</span>
                </div>
              </li>
            </>
          )}
        </ul>

        <div className="sidebar-footer">
          <div className="status-indicator">
            <span className="detail-label">API Server Status:</span>
            {apiLoading ? (
              <RefreshCw size={14} className="animate-spin text-gray-400" />
            ) : apiOnline ? (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <div className="dot" />
                <span style={{ color: 'var(--success)', fontWeight: '600' }}>Active</span>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <div className="dot" style={{ backgroundColor: 'var(--danger)', boxShadow: '0 0 8px var(--danger)' }} />
                <span style={{ color: 'var(--danger)', fontWeight: '600' }}>Offline</span>
              </div>
            )}
          </div>
          <div className="status-indicator">
            <span className="detail-label">User:</span>
            <span style={{ color: 'var(--text-primary)', fontWeight: '600', fontSize: '12px', maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {currentUser?.full_name || currentUser?.email || 'Guest'}
            </span>
          </div>
          <button
            onClick={onLogout}
            style={{
              width: '100%',
              padding: '8px 12px',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.2)',
              borderRadius: '6px',
              color: 'var(--danger)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              marginTop: '8px',
              fontSize: '13px',
              fontWeight: '600',
              transition: 'all 0.3s ease'
            }}
          >
            <LogOut size={14} />
            Logout
          </button>
        </div>
      </nav>

      {/* Main Content Area */}
      <main className="main-content">
        {!apiOnline && !apiLoading && (
          <div className="glass-card animate-fade-in" style={{ borderColor: 'var(--danger)', marginBottom: '24px', background: 'rgba(239, 68, 68, 0.05)', display: 'flex', alignItems: 'center', gap: '16px' }}>
            <AlertOctagon className="text-red-500" size={36} style={{ color: 'var(--danger)' }} />
            <div>
              <h4 style={{ color: 'var(--danger)', fontWeight: '600', marginBottom: '4px' }}>Backend Service Disconnected</h4>
              <p style={{ color: 'var(--text-secondary)', fontSize: '14px' }}>
                The FastAPI backend server is not running or unreachable. Please launch the backend by running <code>cd backend && python -m uvicorn main:app --reload</code> or checking your port configuration.
              </p>
            </div>
          </div>
        )}

        {/* Tab 1: Interactive Single Comment Analyzer */}
        {activeTab === 'analyzer' && (
          <div className="animate-fade-in">
            <h1 className="title-large">Interactive Comment Analyzer</h1>
            <p className="subtitle">Type a comment in English or Hinglish to run it through the NLP preprocessing and ML classification model.</p>
            
            <div className="analyzer-container">
              {/* Input Form */}
              <div className="glass-card input-section">
                <form onSubmit={handleAnalyze} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <label style={{ fontWeight: '600', fontSize: '15px', color: 'var(--text-primary)' }}>Enter Social Comment</label>
                  <div className="textarea-wrapper">
                    <textarea 
                      className="text-input" 
                      rows={5}
                      placeholder="Type comment here (e.g. 'You are stupid and useless' or Hinglish like 'Tu bahut bada gadha hai')..."
                      value={inputComment}
                      onChange={(e) => setInputComment(e.target.value)}
                      maxLength={300}
                      disabled={!apiOnline}
                    />
                    <span className="char-counter">{inputComment.length}/300</span>
                  </div>
                  <button 
                    type="submit" 
                    className="btn-primary"
                    disabled={!inputComment.trim() || !apiOnline || analysisLoading}
                  >
                    {analysisLoading ? 'Running Classification...' : 'Analyze Comment'}
                  </button>
                </form>
              </div>

              {/* Classification Results */}
              <div className="glass-card analyzer-results-card">
                <div className="result-header">
                  <h3 style={{ fontSize: '14px', textTransform: 'uppercase', letterSpacing: '0.8px', color: 'var(--text-secondary)' }}>AI Prediction</h3>
                  {analysisResult ? (
                    <div className={`category-tag ${analysisResult.category === 'Normal' ? 'normal' : 'toxic'}`}>
                      {analysisResult.category === 'Normal' ? <CheckCircle size={18} /> : <AlertTriangle size={18} />}
                      <span>{analysisResult.category}</span>
                    </div>
                  ) : (
                    <div className="category-tag" style={{ background: 'rgba(255, 255, 255, 0.04)', color: 'var(--text-muted)' }}>
                      <Clock size={18} />
                      <span>Awaiting Input</span>
                    </div>
                  )}
                </div>

                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <div className="detail-row">
                    <span className="detail-label">Sentiment Sentiment</span>
                    <span className="detail-value">
                      {analysisResult ? (
                        <span className={`sentiment-badge ${analysisResult.sentiment.toLowerCase()}`}>
                          {analysisResult.sentiment === 'Positive' ? '😊 ' : analysisResult.sentiment === 'Negative' ? '😞 ' : '😐 '}
                          {analysisResult.sentiment}
                        </span>
                      ) : '-'}
                    </span>
                  </div>

                  <div className="detail-row">
                    <span className="detail-label">Language Model</span>
                    <span className="detail-value">
                      {analysisResult ? (
                        <span className="lang-badge">
                          <Languages size={12} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />
                          {analysisResult.language}
                        </span>
                      ) : '-'}
                    </span>
                  </div>

                  <div className="detail-row" style={{ flexDirection: 'column', alignItems: 'stretch' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span className="detail-label">Model Confidence</span>
                      <span className="detail-value" style={{ color: analysisResult?.category === 'Normal' ? 'var(--success)' : 'var(--danger)' }}>
                        {analysisResult ? `${(analysisResult.confidence * 100).toFixed(1)}%` : '-'}
                      </span>
                    </div>
                    {analysisResult && (
                      <div className="meter-container">
                        <div className="meter-track">
                          <div 
                            className={`meter-bar ${analysisResult.category === 'Normal' ? 'normal' : 'toxic'}`} 
                            style={{ width: `${analysisResult.confidence * 100}%` }}
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="detail-row" style={{ flexDirection: 'column', alignItems: 'flex-start', borderBottom: 'none', marginTop: '10px' }}>
                    <span className="detail-label" style={{ marginBottom: '8px' }}>NLP Preprocessed Text</span>
                    <div style={{ 
                      width: '100%', 
                      background: 'rgba(0, 0, 0, 0.2)', 
                      borderRadius: '8px', 
                      padding: '10px 14px', 
                      fontSize: '13px', 
                      fontFamily: 'monospace', 
                      border: '1px solid var(--border-color)',
                      color: analysisResult?.cleaned_text ? 'var(--primary-hover)' : 'var(--text-muted)',
                      minHeight: '40px',
                      wordBreak: 'break-all'
                    }}>
                      {analysisResult ? (analysisResult.cleaned_text || '[No words left after stopword filtering]') : 'Output will display here...'}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Live Chat Simulation Panel */}
        {activeTab === 'chat' && (
          <div className="animate-fade-in" style={{ height: '100%' }}>
            <h1 className="title-large">Moderated Live Chat Simulator</h1>
            <p className="subtitle">Simulate an online community chat room. The ML model intercepts toxic messages in real-time, masking them with a warning blur.</p>

            <div className="glass-card chat-container">
              {/* Users list */}
              <div className="chat-users-panel">
                <h3>Active Users</h3>
                <ul className="user-list">
                  <li className="user-item">
                    <div className="user-avatar" style={{ background: 'var(--primary)' }}>Y</div>
                    <span style={{ fontWeight: '600' }}>You</span>
                    <div className="user-status-dot" />
                  </li>
                  <li className="user-item">
                    <div className="user-avatar" style={{ background: 'var(--success)' }}>A</div>
                    <span>Alice</span>
                    <div className="user-status-dot" />
                  </li>
                  <li className="user-item">
                    <div className="user-avatar" style={{ background: 'var(--info)' }}>B</div>
                    <span>Bob</span>
                    <div className="user-status-dot" />
                  </li>
                  <li className="user-item">
                    <div className="user-avatar" style={{ background: 'var(--warning)' }}>R</div>
                    <span>Rahul</span>
                    <div className="user-status-dot" />
                  </li>
                  <li className="user-item">
                    <div className="user-avatar" style={{ background: 'var(--danger)' }}>P</div>
                    <span>Priya</span>
                    <div className="user-status-dot" />
                  </li>
                </ul>
                <div style={{ marginTop: 'auto', background: 'rgba(245, 158, 11, 0.1)', padding: '10px', borderRadius: '8px', border: '1px solid rgba(245, 158, 11, 0.2)', fontSize: '11px', color: 'var(--warning)', display: 'flex', gap: '6px' }}>
                  <AlertOctagon size={18} style={{ flexShrink: 0 }} />
                  <span>Other members will post randomly to simulate chat moderation.</span>
                </div>
              </div>

              {/* Chat Feed */}
              <div className="chat-feed-panel">
                <div className="chat-messages">
                  {chatMessages.length === 0 ? (
                    <div className="empty-state">
                      <MessageSquare size={36} className="text-gray-600" />
                      <span>No messages in history. Start typing below!</span>
                    </div>
                  ) : (
                    chatMessages.map((msg, index) => {
                      const isMe = msg.sender === 'You';
                      const showOverlay = msg.flagged && !revealedMessages.has(index);

                      return (
                        <div key={index} className={`chat-msg-bubble ${isMe ? 'me' : ''}`}>
                          <div className="chat-msg-info">
                            <span className="chat-msg-sender">{msg.sender}</span>
                            <span>{new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
                            {msg.flagged && (
                              <span className="alert-pill">
                                {msg.category}
                              </span>
                            )}
                          </div>
                          
                          <div 
                            className={`chat-msg-content ${showOverlay ? 'flagged-obscured' : ''}`}
                            onClick={() => showOverlay && toggleRevealMessage(index)}
                          >
                            <p>{msg.text}</p>
                            {showOverlay && (
                              <div className="reveal-prompt">
                                <AlertTriangle size={14} style={{ marginRight: '6px' }} />
                                <span>Masked message. Click to view.</span>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })
                  )}
                  <div ref={chatEndRef} />
                </div>

                {/* Message Input Box */}
                <form onSubmit={handleSendChatMessage} className="chat-input-bar">
                  <input 
                    type="text"
                    className="text-input"
                    placeholder={apiOnline ? "Type a message... try 'Stupid idiot' or 'Rahul is a good programmer'" : "API Offline - chat input disabled"}
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    disabled={!apiOnline}
                  />
                  <button type="submit" className="btn-primary" disabled={!chatInput.trim() || !apiOnline}>
                    <Send size={16} />
                    <span>Send</span>
                  </button>
                </form>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Admin Analytics Dashboard */}
        {activeTab === 'dashboard' && (
          <div className="animate-fade-in">
            <h1 className="title-large">System Analytics Dashboard</h1>
            <p className="subtitle">Real-time stats, daily incident tracking, and lexical distribution of intercepted comments.</p>

            {/* Metrics Grid */}
            <div className="stats-grid">
              <div className="glass-card stat-card">
                <div className="stat-info">
                  <h3>Total Analyzed</h3>
                  <p>{analytics.total_comments}</p>
                </div>
                <div className="stat-icon-wrapper purple">
                  <Globe size={24} />
                </div>
              </div>

              <div className="glass-card stat-card">
                <div className="stat-info">
                  <h3>Toxic Comments</h3>
                  <p>{analytics.toxic_comments}</p>
                  <span style={{ fontSize: '11px', color: 'var(--danger)', fontWeight: '600' }}>
                    {analytics.total_comments ? ((analytics.toxic_comments / analytics.total_comments) * 100).toFixed(1) : 0}% Toxic Rate
                  </span>
                </div>
                <div className="stat-icon-wrapper red">
                  <AlertOctagon size={24} />
                </div>
              </div>

              <div className="glass-card stat-card">
                <div className="stat-info">
                  <h3>Clean Comments</h3>
                  <p>{analytics.clean_comments}</p>
                  <span style={{ fontSize: '11px', color: 'var(--success)', fontWeight: '600' }}>
                    {analytics.total_comments ? ((analytics.clean_comments / analytics.total_comments) * 100).toFixed(1) : 0}% Safety Rate
                  </span>
                </div>
                <div className="stat-icon-wrapper green">
                  <CheckCircle size={24} />
                </div>
              </div>
            </div>

            {/* Charts Grid */}
            <div className="dashboard-grid">
              {/* Line Trend Chart */}
              <div className="glass-card chart-card">
                <h3>Incident Volume Trend (7 Days)</h3>
                <div className="chart-wrapper">
                  {analytics.trends.length ? (
                    <Line data={prepareLineData()} options={chartOptions} />
                  ) : (
                    <span className="text-gray-500">Awaiting data...</span>
                  )}
                </div>
              </div>

              {/* Category Doughnut Chart */}
              <div className="glass-card chart-card">
                <h3>Cyberbullying Categories Distribution</h3>
                <div className="chart-wrapper">
                  {Object.keys(analytics.categories).length > 1 ? (
                    <Doughnut 
                      data={prepareDoughnutData()} 
                      options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                          legend: {
                            position: 'right',
                            labels: {
                              color: '#94a3b8',
                              font: { family: 'Outfit', size: 11 }
                            }
                          }
                        }
                      }} 
                    />
                  ) : (
                    <span className="text-gray-500">No toxic logs recorded yet.</span>
                  )}
                </div>
              </div>
            </div>

            <div className="dashboard-grid" style={{ gridTemplateColumns: '1.2fr 1fr' }}>
              {/* Sentiment Chart */}
              <div className="glass-card chart-card">
                <h3>Social Sentiment Analysis</h3>
                <div className="chart-wrapper">
                  {Object.keys(analytics.sentiment).length ? (
                    <Bar data={prepareBarData()} options={chartOptions} />
                  ) : (
                    <span className="text-gray-500">Awaiting sentiment logs...</span>
                  )}
                </div>
              </div>

              {/* Word Cloud/Frequency Cards */}
              <div className="glass-card chart-card">
                <h3>Top Flagged Keywords</h3>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                  Frequently flagged keywords in toxic comments (excluding common stopwords).
                </p>
                {analytics.top_abusive_words.length === 0 ? (
                  <div className="empty-state" style={{ flex: 1 }}>
                    <AlertTriangle size={24} className="text-gray-600" />
                    <span style={{ fontSize: '14px' }}>No flagged words detected yet.</span>
                  </div>
                ) : (
                  <div className="top-words-container">
                    {analytics.top_abusive_words.map((item, index) => (
                      <span key={index} className="word-pill">
                        <span>{item.word}</span>
                        <span className="word-count">{item.count}</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Model Info & Historical Logs */}
        {activeTab === 'metrics' && (
          <div className="animate-fade-in">
            <h1 className="title-large">Model Engineering & History Logs</h1>
            <p className="subtitle">Technical pipeline architecture, classification metrics, and audit log history.</p>

            <div className="model-info-container">
              {/* Model Description */}
              <div className="glass-card info-card">
                <h3>Model Engineering Details</h3>
                <p>
                  This system implements a fast, robust classification pipeline using a <strong>TF-IDF Vectorizer + Logistic Regression</strong> with balanced class weighting.
                </p>
                <p>
                  To maximize efficiency on local machines, features are extracted dynamically using unigram and bigram word tokens. Custom token filters clean punctuation, links, and tags while preserving negation terms.
                </p>
                <ul className="info-list">
                  <li>
                    <div className="bullet-dot" />
                    <strong>Dataset:</strong> Augmented multi-class English + Hinglish dataset (1000+ templates)
                  </li>
                  <li>
                    <div className="bullet-dot" />
                    <strong>Vectorizer Parameters:</strong> Ngram range (1, 2), Sublinear TF scaling
                  </li>
                  <li>
                    <div className="bullet-dot" />
                    <strong>Classifier Parameters:</strong> class_weight='balanced', C=10.0, max_iter=1000
                  </li>
                  <li>
                    <div className="bullet-dot" />
                    <strong>Accuracy:</strong> 99%+ on representational datasets
                  </li>
                </ul>
              </div>

              {/* Language Metrics */}
              <div className="glass-card info-card">
                <h3>Bilingual NLP & Hinglish Support</h3>
                <p>
                  Traditional NLP filters fail on <strong>Hinglish</strong> (Hindi phrases typed in the Roman alphabet, e.g., "tum ek pagl ho") due to phonetic spelling variations.
                </p>
                <p>
                  Our pipeline implements a language-splitting layer that calculates phonetic match ratios against a consolidated dictionary of pronouns, particles, and common verbs.
                </p>
                <ul className="info-list">
                  <li>
                    <div className="bullet-dot" />
                    <strong>Phonetic normalizer:</strong> Clears multiple vowels and normalizes phonetic repeats
                  </li>
                  <li>
                    <div className="bullet-dot" />
                    <strong>Stopwords:</strong> Union of English and Romanized Hindi stopwords
                  </li>
                  <li>
                    <div className="bullet-dot" />
                    <strong>Languages detected:</strong> English, Hinglish/Hindi
                  </li>
                </ul>
              </div>
            </div>

            {/* Audit Logs Table */}
            <div className="glass-card table-card">
              <div className="table-header">
                <div>
                  <h3 style={{ fontSize: '16px', fontWeight: '600' }}>Comment Inspection Log</h3>
                  <p style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>Audit records of all processed text comments.</p>
                </div>
                <div style={{ display: 'flex', gap: '12px', width: '60%' }}>
                  <input 
                    type="text"
                    className="text-input table-search"
                    placeholder="Search logs..."
                    value={logsSearch}
                    onChange={(e) => setLogsSearch(e.target.value)}
                  />
                  <button 
                    onClick={handleClearLogs} 
                    className="btn-secondary" 
                    style={{ color: 'var(--danger)', borderColor: 'rgba(239, 68, 68, 0.15)', display: 'flex', alignItems: 'center', gap: '8px' }}
                  >
                    <Trash2 size={16} />
                    <span>Clear Data</span>
                  </button>
                </div>
              </div>

              <div className="table-wrapper">
                {filteredLogs.length === 0 ? (
                  <div className="empty-state">
                    <Trash2 size={36} className="text-gray-600" />
                    <span>No logs found matching your filter criteria.</span>
                  </div>
                ) : (
                  <table className="custom-table">
                    <thead>
                      <tr>
                        <th>Time</th>
                        <th>Comment Text</th>
                        <th>Language</th>
                        <th>Sentiment</th>
                        <th>Category</th>
                        <th>Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredLogs.map((log) => (
                        <tr key={log.id}>
                          <td style={{ whiteSpace: 'nowrap', color: 'var(--text-muted)' }}>
                            {new Date(log.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </td>
                          <td style={{ maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                            {log.text}
                          </td>
                          <td>
                            <span className="lang-badge" style={{ fontSize: '11px' }}>{log.language}</span>
                          </td>
                          <td>
                            <span className={`sentiment-badge ${log.sentiment.toLowerCase()}`} style={{ fontSize: '11px' }}>
                              {log.sentiment}
                            </span>
                          </td>
                          <td>
                            <span className={`sentiment-badge ${log.category === 'Normal' ? 'positive' : 'negative'}`} style={{ fontSize: '11px', fontWeight: '600' }}>
                              {log.category}
                            </span>
                          </td>
                          <td style={{ fontWeight: '600' }}>
                            {(log.confidence * 100).toFixed(0)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default Dashboard;
