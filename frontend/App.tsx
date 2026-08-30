import { StatusBar } from 'expo-status-bar';
import { StyleSheet, View } from 'react-native';
import UploadZone from './src/features/upload/UploadZone';

export default function App() {
  return (
    <View style={styles.root}>
      <StatusBar style="light" />
      <UploadZone />
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: '#020617',
  },
});
