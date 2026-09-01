import { useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, View, Text, TouchableOpacity } from 'react-native';
import { UploadZone } from './src/features/upload/UploadZone';
import { PrivoCameraView } from './src/features/camera/CameraView';

type Tab = 'gallery' | 'camera';

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('gallery');

  return (
    <View style={styles.root}>
      <StatusBar style="light" />

      {/* Screen */}
      <View style={styles.screen}>
        {activeTab === 'gallery' ? <UploadZone /> : <PrivoCameraView />}
      </View>

      {/* Tab bar */}
      <View style={styles.tabBar}>
        <TouchableOpacity
          style={styles.tab}
          onPress={() => setActiveTab('gallery')}
          activeOpacity={0.7}
        >
          <Text style={styles.tabIcon}>🖼️</Text>
          <Text style={[styles.tabLabel, activeTab === 'gallery' && styles.tabLabelActive]}>
            Gallery
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.tab}
          onPress={() => setActiveTab('camera')}
          activeOpacity={0.7}
        >
          <Text style={styles.tabIcon}>📷</Text>
          <Text style={[styles.tabLabel, activeTab === 'camera' && styles.tabLabelActive]}>
            Camera
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#020617',
  },
  screen: {
    flex: 1,
  },
  tabBar: {
    flexDirection: 'row',
    backgroundColor: '#0F172A',
    borderTopWidth: 1,
    borderTopColor: '#1E293B',
    paddingBottom: 8,
  },
  tab: {
    flex: 1,
    alignItems: 'center',
    paddingTop: 10,
    paddingBottom: 4,
    gap: 2,
  },
  tabIcon: {
    fontSize: 22,
  },
  tabLabel: {
    fontSize: 11,
    color: '#475569',
    fontWeight: '500',
  },
  tabLabelActive: {
    color: '#8B5CF6',
  },
});
